"""Validation Agent: checks mesh quality and manufacturability."""

from __future__ import annotations

import logging
import math
from typing import List, Optional

import numpy as np
import trimesh

from ..models.manufacturing import (
    IssueSeverity,
    ManufacturingType,
    MeshStats,
    ValidationIssue,
    ValidationResult,
)

logger = logging.getLogger(__name__)

# Manufacturing constraints
CONSTRAINTS = {
    ManufacturingType.CNC_3AXIS: {
        "min_wall_thickness_mm": 0.8,
        "min_feature_size_mm": 0.5,
        "max_aspect_ratio": 10.0,
    },
    ManufacturingType.PRINTING_3D: {
        "min_wall_thickness_mm": 0.4,
        "max_overhang_angle_deg": 45.0,
        "min_feature_size_mm": 0.2,
    },
    ManufacturingType.LASER_CUTTING: {
        "min_feature_size_mm": 0.3,
        "max_depth_mm": 0.0,  # flat only
    },
}


class ValidationAgent:
    """Validate mesh geometry for general quality and manufacturing constraints."""

    async def validate_mesh(
        self,
        mesh: trimesh.Trimesh,
        manufacturing_type: Optional[str] = None,
    ) -> ValidationResult:
        """Validate the mesh and return a ValidationResult."""
        issues: List[ValidationIssue] = []

        # ---------------------------------------------------------------- #
        # Basic geometry checks                                             #
        # ---------------------------------------------------------------- #
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="EMPTY_MESH",
                message="Mesh has no vertices or faces",
            ))
            return ValidationResult(is_valid=False, issues=issues)

        if not mesh.is_watertight:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="NOT_WATERTIGHT",
                message="Mesh is not watertight (has open boundaries)",
                suggestion="Use ManifoldResolver to fix holes",
            ))

        if not mesh.is_volume:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="NOT_MANIFOLD",
                message="Mesh is not a valid solid volume",
                suggestion="Check for non-manifold edges",
            ))

        # Self-intersections (expensive; skip for very large meshes)
        if len(mesh.faces) < 5000:
            try:
                if mesh.is_self_intersecting:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="SELF_INTERSECTING",
                        message="Mesh contains self-intersecting faces",
                        suggestion="Re-run CSG boolean operation with manifold backends",
                    ))
            except Exception:
                pass

        # Degenerate faces
        degen_count = int(np.sum(mesh.area_faces < 1e-10))
        if degen_count > 0:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="DEGENERATE_FACES",
                message=f"{degen_count} degenerate face(s) detected",
                suggestion="Run remove_degenerate_faces()",
            ))

        # ---------------------------------------------------------------- #
        # Wall thickness (approximate via voxel sampling)                  #
        # ---------------------------------------------------------------- #
        min_wall = self._estimate_min_wall_thickness(mesh)

        # ---------------------------------------------------------------- #
        # Manufacturing-specific checks                                     #
        # ---------------------------------------------------------------- #
        mfg_type = None
        if manufacturing_type:
            try:
                mfg_type = ManufacturingType(manufacturing_type)
            except ValueError:
                pass

        if mfg_type:
            issues.extend(self._check_manufacturing(mesh, mfg_type, min_wall))

        # ---------------------------------------------------------------- #
        # Build stats                                                       #
        # ---------------------------------------------------------------- #
        bounds = mesh.bounds
        bbox = {}
        if bounds is not None:
            size = bounds[1] - bounds[0]
            bbox = {"x": float(size[0]), "y": float(size[1]), "z": float(size[2])}

        stats = MeshStats(
            vertex_count=len(mesh.vertices),
            face_count=len(mesh.faces),
            volume=float(abs(mesh.volume)) if mesh.is_volume else 0.0,
            surface_area=float(mesh.area),
            bounding_box=bbox,
            is_watertight=mesh.is_watertight,
            is_manifold=mesh.is_volume,
        )

        has_errors = any(i.severity == IssueSeverity.ERROR for i in issues)

        # ---------------------------------------------------------------- #
        # Build ranked remediation hints                                    #
        # ---------------------------------------------------------------- #
        remediation_hints = self._build_remediation_hints(issues, mesh, mfg_type, min_wall)

        return ValidationResult(
            is_valid=not has_errors,
            issues=issues,
            mesh_stats=stats,
            manufacturing_type=manufacturing_type,
            min_wall_thickness=min_wall,
            max_overhang_angle=self._max_overhang_angle(mesh) if mfg_type == ManufacturingType.PRINTING_3D else None,
            remediation_hints=remediation_hints,
        )

    def _check_manufacturing(
        self,
        mesh: trimesh.Trimesh,
        mfg_type: ManufacturingType,
        min_wall: Optional[float],
    ) -> List[ValidationIssue]:
        issues: List[ValidationIssue] = []
        constraints = CONSTRAINTS.get(mfg_type, {})

        if mfg_type == ManufacturingType.PRINTING_3D:
            # Overhang angle
            max_overhang = constraints.get("max_overhang_angle_deg", 45.0)
            actual_max = self._max_overhang_angle(mesh)
            if actual_max and actual_max > max_overhang:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="OVERHANG_ANGLE",
                    message=f"Maximum overhang angle {actual_max:.1f}° exceeds {max_overhang}°",
                    suggestion="Add support structures or reorient the part",
                ))
            # Min wall thickness
            min_allowed = constraints.get("min_wall_thickness_mm", 0.4)
            if min_wall is not None and min_wall < min_allowed:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="THIN_WALL",
                    message=f"Wall thickness {min_wall:.2f}mm below minimum {min_allowed}mm for 3D printing",
                    suggestion="Increase wall thickness",
                ))

        elif mfg_type == ManufacturingType.CNC_3AXIS:
            min_allowed = constraints.get("min_wall_thickness_mm", 0.8)
            if min_wall is not None and min_wall < min_allowed:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="THIN_WALL",
                    message=f"Wall thickness {min_wall:.2f}mm below minimum {min_allowed}mm for CNC",
                    suggestion="Increase wall thickness to at least 0.8mm",
                ))
            # Aspect ratio check
            if mesh.bounds is not None:
                size = mesh.bounds[1] - mesh.bounds[0]
                max_ar = constraints.get("max_aspect_ratio", 10.0)
                nonzero = size[size > 0]
                if len(nonzero) >= 2 and (nonzero.max() / nonzero.min()) > max_ar:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="HIGH_ASPECT_RATIO",
                        message=f"Part aspect ratio exceeds {max_ar}:1 — risk of chatter/deflection",
                        suggestion="Add support features or reduce length",
                    ))

        elif mfg_type == ManufacturingType.LASER_CUTTING:
            if mesh.bounds is not None:
                size = mesh.bounds[1] - mesh.bounds[0]
                if size[2] > 0.1:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="NOT_FLAT",
                        message="Laser cutting requires flat 2D profiles; part has Z depth",
                        suggestion="Use the top-down projection profile for cutting",
                    ))

        return issues

    @staticmethod
    def _estimate_min_wall_thickness(mesh: trimesh.Trimesh) -> Optional[float]:
        """Approximate minimum wall thickness via ray-casting."""
        try:
            if not mesh.is_watertight or len(mesh.faces) == 0:
                return None
            bounds = mesh.bounds
            if bounds is None:
                return None
            # Sample a grid of rays along Z axis
            xs = np.linspace(bounds[0][0] + 0.1, bounds[1][0] - 0.1, 5)
            ys = np.linspace(bounds[0][1] + 0.1, bounds[1][1] - 0.1, 5)
            thicknesses = []
            for x in xs:
                for y in ys:
                    origins = np.array([[x, y, bounds[0][2] - 1.0]])
                    dirs = np.array([[0.0, 0.0, 1.0]])
                    hits, _, _ = mesh.ray.intersects_location(origins, dirs)
                    if len(hits) >= 2:
                        zvals = sorted(hits[:, 2].tolist())
                        for i in range(1, len(zvals)):
                            t = zvals[i] - zvals[i - 1]
                            if t > 0.01:
                                thicknesses.append(t)
            return float(min(thicknesses)) if thicknesses else None
        except Exception as exc:
            logger.debug("min_wall_thickness estimation failed: %s", exc)
            return None

    @staticmethod
    def _max_overhang_angle(mesh: trimesh.Trimesh) -> Optional[float]:
        """Return the maximum overhang angle (degrees from horizontal)."""
        try:
            normals = mesh.face_normals
            z_comp = normals[:, 2]
            # Faces pointing downward (z < 0) are overhangs
            overhang_mask = z_comp < 0
            if not overhang_mask.any():
                return 0.0
            min_z = float(z_comp[overhang_mask].min())
            angle = math.degrees(math.acos(max(-1.0, min(-min_z, 1.0)))) - 90.0
            return round(max(0.0, angle), 1)
        except Exception:
            return None

    @staticmethod
    def _build_remediation_hints(
        issues: List[ValidationIssue],
        mesh: trimesh.Trimesh,
        mfg_type: Optional[ManufacturingType],
        min_wall: Optional[float],
    ) -> List[str]:
        """Generate ranked, actionable remediation hints from validation issues."""
        hints: List[str] = []

        # Group by code for concise hints
        codes = {i.code for i in issues}

        # Error-priority hints first
        if "EMPTY_MESH" in codes:
            hints.append(
                "[ERROR] Mesh has no geometry. Verify your shape description includes "
                "recognizable primitives (box, cylinder, sphere, cone, torus)."
            )

        if "SELF_INTERSECTING" in codes:
            hints.append(
                "[ERROR] Self-intersecting mesh: re-run the boolean operation using the "
                "'manifold' backend, or slightly offset the tool geometry to avoid "
                "coplanar faces."
            )

        if "THIN_WALL" in codes:
            min_w = min_wall or 0.0
            process_label = mfg_type.value if mfg_type else "the selected process"
            hints.append(
                f"[ERROR] Wall thickness {min_w:.2f} mm is below the minimum for "
                f"{process_label}. Increase wall thickness or choose a higher-resolution "
                "process (e.g. SLA for thin features)."
            )

        # Warning-priority hints
        if "NOT_WATERTIGHT" in codes:
            hints.append(
                "[WARNING] Non-watertight mesh: run the ManifoldResolver to fill open "
                "boundaries before exporting for manufacturing."
            )

        if "NOT_MANIFOLD" in codes:
            hints.append(
                "[WARNING] Non-manifold geometry detected. Check for internal faces or "
                "T-junctions introduced by boolean operations."
            )

        if "OVERHANG_ANGLE" in codes:
            hints.append(
                "[WARNING] Overhang angle exceeds 45°. Either add support structures, "
                "reorient the part (Z-axis along tallest dimension), or switch to SLS "
                "which does not require supports."
            )

        if "HIGH_ASPECT_RATIO" in codes:
            hints.append(
                "[WARNING] High aspect ratio detected. For CNC, add a stub/boss for "
                "workholding or reduce the unsupported length to avoid chatter."
            )

        if "NOT_FLAT" in codes:
            hints.append(
                "[WARNING] Laser cutting requires a flat 2D profile. Use the top-down "
                "(XY) projection, or break the model into flat sub-parts."
            )

        if "DEGENERATE_FACES" in codes:
            hints.append(
                "[INFO] Degenerate faces found. Run remove_degenerate_faces() and "
                "merge_vertices() before exporting."
            )

        return hints
