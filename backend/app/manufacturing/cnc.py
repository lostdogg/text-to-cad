"""3-axis CNC manufacturing optimizer."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import trimesh

from ..models.manufacturing import CNCParams, CostEstimate, TimeEstimate, ValidationIssue, IssueSeverity
from .optimizer import BaseManufacturingOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

# Material machinability presets
MATERIAL_PRESETS: Dict[str, Dict[str, Any]] = {
    "aluminum": {"sfm": 800, "chip_load": 0.002, "cost_per_min": 1.2, "density": 2.7},
    "steel": {"sfm": 300, "chip_load": 0.001, "cost_per_min": 2.0, "density": 7.85},
    "plastic": {"sfm": 1200, "chip_load": 0.004, "cost_per_min": 0.8, "density": 1.2},
    "wood": {"sfm": 1500, "chip_load": 0.006, "cost_per_min": 0.5, "density": 0.7},
}


@dataclass
class Toolpath:
    operation: str  # "facing" | "contouring" | "pocketing" | "drilling"
    points: List[Tuple[float, float, float]] = field(default_factory=list)
    feed_rate: float = 1000.0
    depth: float = 0.0


@dataclass
class FixtureSpec:
    workholding: str = "vise"
    datum_face: str = "bottom"
    clamp_clearance_mm: float = 10.0
    notes: str = ""


@dataclass
class AccessibilityReport:
    accessible_faces: int = 0
    inaccessible_faces: int = 0
    accessibility_ratio: float = 1.0
    undercut_detected: bool = False
    notes: str = ""


class CNCOptimizer(BaseManufacturingOptimizer):
    """3-axis CNC machining optimizer."""

    def optimize(self, mesh: trimesh.Trimesh) -> OptimizationResult:
        params = CNCParams()
        toolpaths = self.generate_toolpaths(mesh, params.tool_diameter, params.material)
        fixture = self.optimize_fixturing(mesh)
        accessibility = self.check_accessibility(mesh)
        return OptimizationResult(
            success=True,
            notes=f"Generated {len(toolpaths)} toolpath(s). {accessibility.notes}",
            data={
                "toolpath_count": len(toolpaths),
                "fixture": fixture.__dict__,
                "accessibility": accessibility.__dict__,
            },
        )

    def estimate_cost(self, mesh: trimesh.Trimesh, params: Any = None) -> CostEstimate:
        if params is None:
            params = CNCParams()
        preset = MATERIAL_PRESETS.get(params.material.lower(), MATERIAL_PRESETS["aluminum"])
        time_est = self.estimate_time(mesh, params)
        machine_cost = time_est.total_time * preset["cost_per_min"]
        vol_cm3 = self.mesh_volume(mesh) / 1000.0
        mat_cost = vol_cm3 * preset["density"] * 0.008  # ~$0.008/g as rough estimate
        return CostEstimate(
            material_cost=round(mat_cost, 2),
            machine_cost=round(machine_cost, 2),
            labour_cost=round(time_est.setup_time * 0.5, 2),
            total_cost=round(mat_cost + machine_cost + time_est.setup_time * 0.5, 2),
        )

    def estimate_time(self, mesh: trimesh.Trimesh, params: Any = None) -> TimeEstimate:
        if params is None:
            params = CNCParams()
        preset = MATERIAL_PRESETS.get(params.material.lower(), MATERIAL_PRESETS["aluminum"])
        surface_area_mm2 = self.surface_area(mesh)
        # Rough: machining time ~ surface / (feed_rate * tool_width * step_over)
        step_over = params.tool_diameter * 0.4
        path_length = surface_area_mm2 / step_over
        machining_min = path_length / params.feed_rate
        setup_min = 15.0
        return TimeEstimate(
            setup_time=round(setup_min, 1),
            machining_time=round(machining_min, 1),
            total_time=round(setup_min + machining_min, 1),
        )

    def generate_toolpaths(
        self,
        mesh: trimesh.Trimesh,
        tool_diameter: float = 6.0,
        material: str = "aluminum",
    ) -> List[Toolpath]:
        """Generate facing, contouring, and optional drilling toolpaths."""
        toolpaths: List[Toolpath] = []
        if mesh.bounds is None:
            return toolpaths

        preset = MATERIAL_PRESETS.get(material.lower(), MATERIAL_PRESETS["aluminum"])
        sfm = preset["sfm"]
        feed_rate = math.pi * tool_diameter * sfm / (math.pi * tool_diameter) * 10  # simplified

        min_b, max_b = mesh.bounds[0], mesh.bounds[1]
        step = tool_diameter * 0.8

        # Facing toolpath
        facing = Toolpath(operation="facing", feed_rate=feed_rate, depth=max_b[2])
        y = min_b[1]
        while y <= max_b[1] + step:
            facing.points.append((min_b[0], y, max_b[2]))
            facing.points.append((max_b[0], y, max_b[2]))
            y += step
        toolpaths.append(facing)

        # Contouring toolpath (perimeter)
        contour = Toolpath(operation="contouring", feed_rate=feed_rate * 0.6, depth=min_b[2])
        contour.points = [
            (min_b[0], min_b[1], min_b[2]),
            (max_b[0], min_b[1], min_b[2]),
            (max_b[0], max_b[1], min_b[2]),
            (min_b[0], max_b[1], min_b[2]),
            (min_b[0], min_b[1], min_b[2]),
        ]
        toolpaths.append(contour)

        # Check for circular features -> drilling
        circular = self._detect_circular_features(mesh, tool_diameter)
        for cx, cy, radius in circular:
            drill = Toolpath(
                operation="drilling",
                feed_rate=feed_rate * 0.3,
                depth=min_b[2],
            )
            drill.points = [(cx, cy, max_b[2] + 2), (cx, cy, min_b[2])]
            toolpaths.append(drill)

        return toolpaths

    def optimize_fixturing(self, mesh: trimesh.Trimesh) -> FixtureSpec:
        """Determine optimal workholding."""
        if mesh.bounds is None:
            return FixtureSpec(notes="No geometry data")
        size = mesh.bounds[1] - mesh.bounds[0]
        if size[2] < 10:
            return FixtureSpec(workholding="vacuum_plate", datum_face="bottom",
                               notes="Thin part: vacuum plate recommended")
        if size[0] < 80 and size[1] < 80:
            return FixtureSpec(workholding="vise", datum_face="bottom",
                               clamp_clearance_mm=5.0,
                               notes="Standard vise workholding")
        return FixtureSpec(workholding="fixture_plate", datum_face="bottom",
                           clamp_clearance_mm=15.0,
                           notes="Large part: fixture plate with strap clamps")

    def check_accessibility(self, mesh: trimesh.Trimesh) -> AccessibilityReport:
        """Approximate 3-axis accessibility check (Z-axis tool access)."""
        if mesh.bounds is None:
            return AccessibilityReport(notes="No geometry")
        normals = mesh.face_normals
        # Faces with normal pointing roughly down (Z-) are inaccessible from above
        z_normals = normals[:, 2]
        inaccessible = int(np.sum(z_normals < -0.7))
        accessible = len(normals) - inaccessible
        ratio = accessible / max(len(normals), 1)
        undercut = inaccessible > 0
        return AccessibilityReport(
            accessible_faces=accessible,
            inaccessible_faces=inaccessible,
            accessibility_ratio=round(ratio, 3),
            undercut_detected=undercut,
            notes="Undercut features detected - consider 5-axis or flip fixturing" if undercut else "Fully accessible from Z+",
        )

    @staticmethod
    def _detect_circular_features(
        mesh: trimesh.Trimesh, min_radius: float
    ) -> List[Tuple[float, float, float]]:
        """Crude detection of circular holes via vertex clustering in XY plane."""
        results = []
        try:
            xy = mesh.vertices[:, :2]
            bounds = mesh.bounds
            if bounds is None:
                return results
            # Simple: look for dense vertex clusters that form circles
            cx = (bounds[0][0] + bounds[1][0]) / 2
            cy = (bounds[0][1] + bounds[1][1]) / 2
            dists = np.sqrt((xy[:, 0] - cx) ** 2 + (xy[:, 1] - cy) ** 2)
            median_r = float(np.median(dists))
            if min_radius < median_r < 50:
                results.append((cx, cy, median_r))
        except Exception:
            pass
        return results
