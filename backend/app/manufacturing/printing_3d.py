"""3D printing manufacturing optimizer."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import trimesh

from ..models.manufacturing import CostEstimate, PrintParams, TimeEstimate
from .optimizer import BaseManufacturingOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

PRINTER_PRESETS: Dict[str, Dict[str, Any]] = {
    "FDM": {"cost_per_gram": 0.02, "speed_mm3_per_s": 10.0, "resolution": 0.1},
    "SLA": {"cost_per_gram": 0.05, "speed_mm3_per_s": 5.0, "resolution": 0.025},
    "SLS": {"cost_per_gram": 0.08, "speed_mm3_per_s": 3.0, "resolution": 0.08},
}

MATERIAL_DENSITY: Dict[str, float] = {
    "PLA": 1.24, "ABS": 1.05, "PETG": 1.27, "Resin": 1.1, "Nylon": 1.01,
}


@dataclass
class OrientationResult:
    rotation_x: float = 0.0
    rotation_y: float = 0.0
    rotation_z: float = 0.0
    support_volume_mm3: float = 0.0
    z_height_mm: float = 0.0
    notes: str = ""


@dataclass
class SupportStructure:
    volume_mm3: float = 0.0
    contact_points: int = 0
    overhang_area_mm2: float = 0.0
    removable: bool = True


@dataclass
class LayerAnalysis:
    layer_count: int = 0
    layer_height_mm: float = 0.2
    print_time_minutes: float = 0.0
    critical_layers: List[int] = field(default_factory=list)


class PrintingOptimizer(BaseManufacturingOptimizer):
    """3D printing process optimizer."""

    def optimize(self, mesh: trimesh.Trimesh) -> OptimizationResult:
        params = PrintParams()
        orientation = self.optimize_orientation(mesh)
        supports = self.generate_supports(mesh)
        vol = self.estimate_material_volume(mesh)
        analysis = self.layer_analysis(mesh, params.layer_height)
        return OptimizationResult(
            success=True,
            notes=f"Print height {orientation.z_height_mm:.1f}mm, {analysis.layer_count} layers.",
            data={
                "orientation": orientation.__dict__,
                "supports": supports.__dict__,
                "material_volume_mm3": vol,
                "layer_analysis": analysis.__dict__,
            },
        )

    def estimate_cost(self, mesh: trimesh.Trimesh, params: Any = None) -> CostEstimate:
        if params is None:
            params = PrintParams()
        preset = PRINTER_PRESETS.get(params.printer_type, PRINTER_PRESETS["FDM"])
        density = MATERIAL_DENSITY.get(params.material, 1.2)
        vol_mm3 = self.estimate_material_volume(mesh) * (params.infill_percent / 100.0 * 0.8 + 0.2)
        mass_g = vol_mm3 * density / 1000.0
        mat_cost = mass_g * preset["cost_per_gram"]
        time_est = self.estimate_time(mesh, params)
        machine_cost = time_est.total_time / 60.0 * 0.5
        return CostEstimate(
            material_cost=round(mat_cost, 2),
            machine_cost=round(machine_cost, 2),
            labour_cost=0.5,
            total_cost=round(mat_cost + machine_cost + 0.5, 2),
        )

    def estimate_time(self, mesh: trimesh.Trimesh, params: Any = None) -> TimeEstimate:
        if params is None:
            params = PrintParams()
        preset = PRINTER_PRESETS.get(params.printer_type, PRINTER_PRESETS["FDM"])
        vol_mm3 = self.estimate_material_volume(mesh)
        print_time_s = vol_mm3 / preset["speed_mm3_per_s"]
        print_time_min = print_time_s / 60.0
        return TimeEstimate(
            setup_time=10.0,
            machining_time=round(print_time_min, 1),
            total_time=round(10.0 + print_time_min, 1),
            notes=f"Estimated print time at {params.layer_height}mm layers",
        )

    def optimize_orientation(self, mesh: trimesh.Trimesh) -> OrientationResult:
        """Find the orientation that minimises support volume."""
        if mesh.bounds is None:
            return OrientationResult(notes="No geometry")
        candidates = [
            (0.0, 0.0, 0.0),
            (90.0, 0.0, 0.0),
            (0.0, 90.0, 0.0),
            (180.0, 0.0, 0.0),
        ]
        best: Optional[Tuple[float, float, float]] = None
        best_score = float("inf")
        for rx, ry, rz in candidates:
            rotated = mesh.copy()
            if rx != 0:
                Rx = trimesh.transformations.rotation_matrix(math.radians(rx), [1, 0, 0])
                rotated.apply_transform(Rx)
            if ry != 0:
                Ry = trimesh.transformations.rotation_matrix(math.radians(ry), [0, 1, 0])
                rotated.apply_transform(Ry)
            support_vol = self._estimate_support_volume(rotated)
            if support_vol < best_score:
                best_score = support_vol
                best = (rx, ry, rz)
        rx, ry, rz = best or (0.0, 0.0, 0.0)
        rotated = mesh.copy()
        if rx != 0:
            rotated.apply_transform(trimesh.transformations.rotation_matrix(math.radians(rx), [1, 0, 0]))
        z_height = float(rotated.bounds[1][2] - rotated.bounds[0][2]) if rotated.bounds is not None else 0.0
        return OrientationResult(
            rotation_x=rx, rotation_y=ry, rotation_z=rz,
            support_volume_mm3=round(best_score, 2),
            z_height_mm=round(z_height, 2),
            notes="Orientation minimises support volume",
        )

    def generate_supports(
        self, mesh: trimesh.Trimesh, angle_threshold: float = 45.0
    ) -> SupportStructure:
        """Identify overhanging faces that need support."""
        threshold_rad = math.radians(angle_threshold)
        normals = mesh.face_normals
        z_component = normals[:, 2]
        overhang_mask = z_component < -math.cos(threshold_rad)
        overhang_faces = mesh.faces[overhang_mask]
        overhang_area = float(np.sum(mesh.area_faces[overhang_mask])) if overhang_mask.any() else 0.0
        support_vol = overhang_area * 2.0  # rough approximation
        return SupportStructure(
            volume_mm3=round(support_vol, 2),
            contact_points=int(len(overhang_faces)),
            overhang_area_mm2=round(overhang_area, 2),
            removable=True,
        )

    def estimate_material_volume(self, mesh: trimesh.Trimesh) -> float:
        """Return filled solid volume in mm³."""
        if mesh.is_volume:
            return float(abs(mesh.volume))
        return self.bounding_box_volume(mesh) * 0.6

    def layer_analysis(
        self, mesh: trimesh.Trimesh, layer_height: float = 0.2
    ) -> LayerAnalysis:
        if mesh.bounds is None:
            return LayerAnalysis()
        height = float(mesh.bounds[1][2] - mesh.bounds[0][2])
        num_layers = max(1, int(math.ceil(height / layer_height)))
        # Identify critical layers (large area changes = bridging/overhang)
        critical = []
        step = max(1, num_layers // 10)
        for i in range(0, num_layers, step):
            z = mesh.bounds[0][2] + i * layer_height
            section = mesh.section(plane_origin=[0, 0, z], plane_normal=[0, 0, 1])
            if section is None:
                critical.append(i)
        total_time = num_layers * layer_height / 60.0 * 100  # rough
        return LayerAnalysis(
            layer_count=num_layers,
            layer_height_mm=layer_height,
            print_time_minutes=round(total_time, 1),
            critical_layers=critical[:5],
        )

    @staticmethod
    def _estimate_support_volume(mesh: trimesh.Trimesh) -> float:
        if mesh.bounds is None:
            return 0.0
        normals = mesh.face_normals
        z_component = normals[:, 2]
        threshold = math.cos(math.radians(45))
        overhang_mask = z_component < -threshold
        if not overhang_mask.any():
            return 0.0
        return float(np.sum(mesh.area_faces[overhang_mask])) * 2.0
