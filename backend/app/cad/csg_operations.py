"""Core CSG (Constructive Solid Geometry) operations using trimesh.

Coordinate system: X+ Right, Y+ Back, Z+ Up.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import trimesh

logger = logging.getLogger(__name__)


class CSGOperations:
    """Provides primitive creation and boolean CSG operations."""

    # ------------------------------------------------------------------ #
    # Primitive constructors                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def create_box(width: float, height: float, depth: float) -> trimesh.Trimesh:
        """Create a box. width=X, depth=Y, height=Z (Z+ Up convention)."""
        mesh = trimesh.creation.box(extents=[width, depth, height])
        return mesh

    @staticmethod
    def create_cylinder(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
        """Create a cylinder aligned with Z axis (Z+ Up convention)."""
        mesh = trimesh.creation.cylinder(radius=radius, height=height, sections=sections)
        return mesh

    @staticmethod
    def create_sphere(radius: float, subdivisions: int = 4) -> trimesh.Trimesh:
        """Create a UV sphere."""
        mesh = trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius)
        return mesh

    @staticmethod
    def create_cone(radius: float, height: float, sections: int = 64) -> trimesh.Trimesh:
        """Create a cone aligned with Z axis."""
        mesh = trimesh.creation.cone(radius=radius, height=height, sections=sections)
        return mesh

    @staticmethod
    def create_torus(
        major_radius: float,
        minor_radius: float,
        major_sections: int = 64,
        minor_sections: int = 32,
    ) -> trimesh.Trimesh:
        """Create a torus in the XY plane (Z+ Up convention)."""
        mesh = trimesh.creation.torus(
            major_radius=major_radius,
            minor_radius=minor_radius,
            major_sections=major_sections,
            minor_sections=minor_sections,
        )
        return mesh

    # ------------------------------------------------------------------ #
    # Boolean operations                                                   #
    # ------------------------------------------------------------------ #

    @classmethod
    def union(cls, mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Boolean union of two meshes."""
        return cls._boolean_op(mesh_a, mesh_b, "union")

    @classmethod
    def intersection(cls, mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Boolean intersection of two meshes."""
        return cls._boolean_op(mesh_a, mesh_b, "intersection")

    @classmethod
    def subtraction(cls, mesh_a: trimesh.Trimesh, mesh_b: trimesh.Trimesh) -> trimesh.Trimesh:
        """Boolean subtraction: mesh_a minus mesh_b."""
        return cls._boolean_op(mesh_a, mesh_b, "difference")

    @classmethod
    def _boolean_op(
        cls,
        mesh_a: trimesh.Trimesh,
        mesh_b: trimesh.Trimesh,
        operation: str,
    ) -> trimesh.Trimesh:
        """Internal boolean operation with graceful fallback."""
        # Primary: trimesh.boolean module functions (union/difference/intersection)
        fn_map = {
            "union": trimesh.boolean.union,
            "difference": trimesh.boolean.difference,
            "intersection": trimesh.boolean.intersection,
        }
        try:
            fn = fn_map.get(operation)
            if fn is not None:
                result = fn([mesh_a, mesh_b])
                if result is not None and len(result.faces) > 0:
                    return result
        except Exception as exc:
            logger.warning("trimesh.boolean.%s failed: %s", operation, exc)

        # Secondary: boolean_manifold with operation keyword
        try:
            result = trimesh.boolean.boolean_manifold(
                [mesh_a, mesh_b], operation=operation
            )
            if result is not None and len(result.faces) > 0:
                return result
        except Exception as exc:
            logger.warning("boolean_manifold fallback failed (%s): %s", operation, exc)

        # Final fallback: return mesh_a unmodified (non-destructive)
        logger.error(
            "All CSG backends failed for '%s'. Returning mesh_a unmodified.", operation
        )
        return mesh_a.copy()

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def apply_transform(
        mesh: trimesh.Trimesh,
        position: Optional[list] = None,
        rotation_deg: Optional[list] = None,
        scale: Optional[list] = None,
    ) -> trimesh.Trimesh:
        """Apply a TRS transform to a mesh and return a copy."""
        mesh = mesh.copy()
        if scale is not None:
            sx, sy, sz = scale
            mesh.apply_scale([sx, sy, sz])
        if rotation_deg is not None:
            rx, ry, rz = [np.radians(a) for a in rotation_deg]
            Rx = trimesh.transformations.rotation_matrix(rx, [1, 0, 0])
            Ry = trimesh.transformations.rotation_matrix(ry, [0, 1, 0])
            Rz = trimesh.transformations.rotation_matrix(rz, [0, 0, 1])
            mesh.apply_transform(Rz @ Ry @ Rx)
        if position is not None:
            T = trimesh.transformations.translation_matrix(position)
            mesh.apply_transform(T)
        return mesh

    @staticmethod
    def mesh_info(mesh: trimesh.Trimesh) -> dict:
        """Return a dict of basic mesh statistics."""
        return {
            "vertex_count": len(mesh.vertices),
            "face_count": len(mesh.faces),
            "is_watertight": mesh.is_watertight,
            "is_volume": mesh.is_volume,
            "volume": float(mesh.volume) if mesh.is_volume else None,
            "surface_area": float(mesh.area),
            "bounds": mesh.bounds.tolist() if mesh.bounds is not None else None,
        }
