"""Manifold mesh resolution utilities.

Detects and fixes common mesh issues: non-manifold edges, degenerate faces,
open holes, duplicate/unreferenced vertices, and flipped normals.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List

import numpy as np
import trimesh

logger = logging.getLogger(__name__)


@dataclass
class ManifoldResult:
    mesh: trimesh.Trimesh
    issues_found: List[str] = field(default_factory=list)
    issues_fixed: List[str] = field(default_factory=list)
    is_watertight: bool = False


class ManifoldResolver:
    """Attempt to produce a watertight, manifold mesh from a potentially broken input."""

    def resolve(self, mesh: trimesh.Trimesh) -> ManifoldResult:
        mesh = mesh.copy()
        issues_found: List[str] = []
        issues_fixed: List[str] = []

        # ---------------------------------------------------------------- #
        # Diagnose                                                          #
        # ---------------------------------------------------------------- #
        if not mesh.is_watertight:
            issues_found.append("mesh_not_watertight")
        if mesh.faces.shape[0] == 0:
            issues_found.append("no_faces")
        if hasattr(mesh, "is_winding_consistent") and not mesh.is_winding_consistent:
            issues_found.append("inconsistent_winding")

        degenerate = self._degenerate_face_count(mesh)
        if degenerate > 0:
            issues_found.append(f"degenerate_faces:{degenerate}")

        # ---------------------------------------------------------------- #
        # Fix: remove degenerate / duplicate faces                         #
        # ---------------------------------------------------------------- #
        try:
            # trimesh 4.x: nondegenerate_faces is a property (bool mask)
            if hasattr(mesh, "nondegenerate_faces"):
                mask = mesh.nondegenerate_faces
                mesh.update_faces(mask)
            else:
                mesh.remove_degenerate_faces()
            # remove_duplicate_faces was renamed / removed in trimesh 4.x
            if hasattr(mesh, "remove_duplicate_faces"):
                mesh.remove_duplicate_faces()
            issues_fixed.append("removed_degenerate_and_duplicate_faces")
        except Exception as exc:
            logger.warning("remove_degenerate_faces failed: %s", exc)

        # ---------------------------------------------------------------- #
        # Fix: merge close / duplicate vertices                            #
        # ---------------------------------------------------------------- #
        try:
            mesh.merge_vertices()
            issues_fixed.append("merged_vertices")
        except Exception as exc:
            logger.warning("merge_vertices failed: %s", exc)

        # ---------------------------------------------------------------- #
        # Fix: fill holes                                                   #
        # ---------------------------------------------------------------- #
        if not mesh.is_watertight:
            try:
                trimesh.repair.fill_holes(mesh)
                issues_fixed.append("fill_holes")
            except Exception as exc:
                logger.warning("fill_holes failed: %s", exc)

        # ---------------------------------------------------------------- #
        # Fix: fix normals                                                  #
        # ---------------------------------------------------------------- #
        try:
            trimesh.repair.fix_normals(mesh)
            issues_fixed.append("fix_normals")
        except Exception as exc:
            logger.warning("fix_normals failed: %s", exc)

        # ---------------------------------------------------------------- #
        # Fix: fix winding                                                  #
        # ---------------------------------------------------------------- #
        try:
            trimesh.repair.fix_winding(mesh)
            issues_fixed.append("fix_winding")
        except Exception as exc:
            logger.warning("fix_winding failed: %s", exc)

        # ---------------------------------------------------------------- #
        # Fix: remove unreferenced vertices                                 #
        # ---------------------------------------------------------------- #
        try:
            mesh.remove_unreferenced_vertices()
            issues_fixed.append("removed_unreferenced_vertices")
        except Exception as exc:
            logger.warning("remove_unreferenced_vertices failed: %s", exc)

        return ManifoldResult(
            mesh=mesh,
            issues_found=issues_found,
            issues_fixed=issues_fixed,
            is_watertight=mesh.is_watertight,
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _degenerate_face_count(mesh: trimesh.Trimesh) -> int:
        """Count faces with zero area."""
        try:
            areas = mesh.area_faces
            return int(np.sum(areas < 1e-10))
        except Exception:
            return 0

    @staticmethod
    def fix_normals(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        mesh = mesh.copy()
        trimesh.repair.fix_normals(mesh)
        return mesh

    @staticmethod
    def fill_holes(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        mesh = mesh.copy()
        trimesh.repair.fill_holes(mesh)
        return mesh

    @staticmethod
    def remove_degenerate_faces(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        mesh = mesh.copy()
        if hasattr(mesh, "nondegenerate_faces"):
            mesh.update_faces(mesh.nondegenerate_faces)
        elif hasattr(mesh, "remove_degenerate_faces"):
            mesh.remove_degenerate_faces()
        return mesh

    @staticmethod
    def merge_vertices(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
        mesh = mesh.copy()
        mesh.merge_vertices()
        return mesh
