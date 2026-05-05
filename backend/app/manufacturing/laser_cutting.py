"""Laser cutting manufacturing optimizer."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import trimesh

from ..models.manufacturing import CostEstimate, LaserParams, TimeEstimate
from .optimizer import BaseManufacturingOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

MATERIAL_PRESETS: Dict[str, Dict[str, Any]] = {
    "acrylic": {"cost_per_m2": 15.0, "density": 1.18, "max_thickness": 20.0},
    "plywood": {"cost_per_m2": 8.0, "density": 0.55, "max_thickness": 18.0},
    "steel_sheet": {"cost_per_m2": 30.0, "density": 7.85, "max_thickness": 6.0},
    "aluminum_sheet": {"cost_per_m2": 25.0, "density": 2.7, "max_thickness": 6.0},
}


@dataclass
class NestingResult:
    sheet_width: float
    sheet_height: float
    parts_placed: int
    efficiency: float  # 0-1
    positions: List[Tuple[float, float, float]] = field(default_factory=list)  # x, y, rotation


class LaserOptimizer(BaseManufacturingOptimizer):
    """Laser cutting process optimizer."""

    def optimize(self, mesh: trimesh.Trimesh) -> OptimizationResult:
        profile = self.extract_profile(mesh)
        if not profile:
            return OptimizationResult(success=False, notes="Could not extract 2D profile")
        nesting = self.nest_parts([profile], sheet_size=(600, 400))
        return OptimizationResult(
            success=True,
            notes=f"Profile extracted ({len(profile)} points). Nesting efficiency: {nesting.efficiency:.1%}",
            data={"profile_points": len(profile), "nesting": nesting.__dict__},
        )

    def estimate_cost(self, mesh: trimesh.Trimesh, params: Any = None) -> CostEstimate:
        if params is None:
            params = LaserParams()
        preset = MATERIAL_PRESETS.get(params.material.lower(), MATERIAL_PRESETS["acrylic"])
        bounds = mesh.bounds
        if bounds is None:
            return CostEstimate()
        area_m2 = ((bounds[1][0] - bounds[0][0]) * (bounds[1][1] - bounds[0][1])) / 1e6
        mat_cost = area_m2 * preset["cost_per_m2"]
        time_est = self.estimate_time(mesh, params)
        machine_cost = time_est.total_time / 60.0 * 0.8
        return CostEstimate(
            material_cost=round(mat_cost, 2),
            machine_cost=round(machine_cost, 2),
            labour_cost=2.0,
            total_cost=round(mat_cost + machine_cost + 2.0, 2),
        )

    def estimate_time(self, mesh: trimesh.Trimesh, params: Any = None) -> TimeEstimate:
        if params is None:
            params = LaserParams()
        profile = self.extract_profile(mesh)
        path_length = self._profile_length(profile)
        cut_time_s = path_length / params.speed * params.passes
        cut_time_min = cut_time_s / 60.0
        return TimeEstimate(
            setup_time=5.0,
            machining_time=round(cut_time_min, 1),
            total_time=round(5.0 + cut_time_min, 1),
        )

    def extract_profile(self, mesh: trimesh.Trimesh) -> List[List[float]]:
        """Extract a 2D XY profile from the bottom face of the mesh."""
        if mesh.bounds is None:
            return []
        z_bottom = float(mesh.bounds[0][2])
        try:
            section = mesh.section(
                plane_origin=[0, 0, z_bottom + 0.01],
                plane_normal=[0, 0, 1],
            )
            if section is None:
                return self._bbox_profile(mesh)
            path2d, _ = section.to_planar()
            if path2d is None or len(path2d.vertices) == 0:
                return self._bbox_profile(mesh)
            return path2d.vertices.tolist()
        except Exception as exc:
            logger.warning("extract_profile failed: %s", exc)
            return self._bbox_profile(mesh)

    def nest_parts(
        self,
        profiles: List[List[List[float]]],
        sheet_size: Tuple[float, float] = (600, 400),
    ) -> NestingResult:
        """Simple bottom-left nesting algorithm."""
        sw, sh = sheet_size
        sheet_area = sw * sh
        positions: List[Tuple[float, float, float]] = []
        used_area = 0.0
        x_cursor = 5.0
        y_cursor = 5.0
        row_height = 0.0
        for profile in profiles:
            if not profile:
                continue
            pts = np.array(profile)
            bbox_w = float(pts[:, 0].max() - pts[:, 0].min()) + 5.0
            bbox_h = float(pts[:, 1].max() - pts[:, 1].min()) + 5.0
            if x_cursor + bbox_w > sw - 5:
                x_cursor = 5.0
                y_cursor += row_height + 5.0
                row_height = 0.0
            if y_cursor + bbox_h > sh - 5:
                break
            positions.append((x_cursor, y_cursor, 0.0))
            used_area += bbox_w * bbox_h
            x_cursor += bbox_w + 5.0
            row_height = max(row_height, bbox_h)
        efficiency = min(1.0, used_area / sheet_area) if positions else 0.0
        return NestingResult(
            sheet_width=sw,
            sheet_height=sh,
            parts_placed=len(positions),
            efficiency=round(efficiency, 3),
            positions=positions,
        )

    def calculate_kerf_compensation(
        self,
        profile: List[List[float]],
        kerf_width: float,
    ) -> List[List[float]]:
        """Offset a 2D profile outward by half the kerf width."""
        if len(profile) < 3:
            return profile
        pts = np.array(profile, dtype=float)
        compensated = []
        n = len(pts)
        half_kerf = kerf_width / 2.0
        for i in range(n):
            p0 = pts[(i - 1) % n]
            p1 = pts[i]
            p2 = pts[(i + 1) % n]
            d1 = p1 - p0
            d2 = p2 - p1
            n1 = np.array([-d1[1], d1[0]])
            n2 = np.array([-d2[1], d2[0]])
            len1 = np.linalg.norm(n1)
            len2 = np.linalg.norm(n2)
            if len1 > 1e-10:
                n1 /= len1
            if len2 > 1e-10:
                n2 /= len2
            avg_normal = n1 + n2
            avg_len = np.linalg.norm(avg_normal)
            if avg_len > 1e-10:
                avg_normal /= avg_len
            compensated.append((p1 + avg_normal * half_kerf).tolist())
        return compensated

    @staticmethod
    def _bbox_profile(mesh: trimesh.Trimesh) -> List[List[float]]:
        """Fallback: return bounding rectangle profile."""
        if mesh.bounds is None:
            return []
        min_b, max_b = mesh.bounds
        return [
            [float(min_b[0]), float(min_b[1])],
            [float(max_b[0]), float(min_b[1])],
            [float(max_b[0]), float(max_b[1])],
            [float(min_b[0]), float(max_b[1])],
            [float(min_b[0]), float(min_b[1])],
        ]

    @staticmethod
    def _profile_length(profile: List[List[float]]) -> float:
        total = 0.0
        for i in range(1, len(profile)):
            dx = profile[i][0] - profile[i-1][0]
            dy = profile[i][1] - profile[i-1][1]
            total += math.sqrt(dx*dx + dy*dy)
        return total
