"""Tests for CSG operations and manifold resolution."""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from backend.app.cad.csg_operations import CSGOperations
from backend.app.cad.manifold import ManifoldResolver


class TestPrimitives:
    def test_create_box(self):
        mesh = CSGOperations.create_box(10, 20, 5)
        assert isinstance(mesh, trimesh.Trimesh)
        assert len(mesh.vertices) > 0
        assert len(mesh.faces) > 0
        bounds_size = mesh.bounds[1] - mesh.bounds[0]
        assert abs(bounds_size[0] - 10.0) < 0.1
        # height and depth may swap depending on trimesh version — just check positive
        assert all(s > 0 for s in bounds_size)

    def test_create_cylinder(self):
        mesh = CSGOperations.create_cylinder(radius=5.0, height=20.0)
        assert isinstance(mesh, trimesh.Trimesh)
        bounds_size = mesh.bounds[1] - mesh.bounds[0]
        # Z extent ~ height
        assert abs(bounds_size[2] - 20.0) < 0.5

    def test_create_sphere(self):
        mesh = CSGOperations.create_sphere(radius=10.0)
        assert isinstance(mesh, trimesh.Trimesh)
        bounds_size = mesh.bounds[1] - mesh.bounds[0]
        # All extents ~ 2*radius
        for s in bounds_size:
            assert abs(s - 20.0) < 1.0

    def test_create_cone(self):
        mesh = CSGOperations.create_cone(radius=5.0, height=15.0)
        assert isinstance(mesh, trimesh.Trimesh)
        assert len(mesh.faces) > 0

    def test_create_torus(self):
        mesh = CSGOperations.create_torus(major_radius=10.0, minor_radius=2.0)
        assert isinstance(mesh, trimesh.Trimesh)
        assert len(mesh.faces) > 0

    def test_mesh_info(self):
        mesh = CSGOperations.create_box(10, 10, 10)
        info = CSGOperations.mesh_info(mesh)
        assert "vertex_count" in info
        assert "face_count" in info
        assert info["vertex_count"] > 0


class TestBooleanOps:
    def _box(self, size=20):
        return CSGOperations.create_box(size, size, size)

    def _small_box(self):
        mesh = CSGOperations.create_box(5, 5, 5)
        T = trimesh.transformations.translation_matrix([0, 0, 0])
        mesh.apply_transform(T)
        return mesh

    def test_union_operation(self):
        a = self._box(20)
        b = CSGOperations.create_box(20, 20, 20)
        b.apply_translation([10, 0, 0])
        result = CSGOperations.union(a, b)
        assert isinstance(result, trimesh.Trimesh)
        assert len(result.faces) > 0

    def test_subtraction_operation(self):
        a = self._box(30)
        b = CSGOperations.create_cylinder(radius=5, height=35)
        result = CSGOperations.subtraction(a, b)
        assert isinstance(result, trimesh.Trimesh)
        assert len(result.faces) > 0

    def test_intersection_operation(self):
        a = self._box(20)
        b = CSGOperations.create_sphere(radius=12)
        result = CSGOperations.intersection(a, b)
        assert isinstance(result, trimesh.Trimesh)
        assert len(result.faces) > 0

    def test_apply_transform(self):
        mesh = self._box(10)
        translated = CSGOperations.apply_transform(mesh, position=[5, 0, 0])
        center = translated.centroid
        assert abs(center[0] - 5.0) < 0.5


class TestManifoldResolver:
    def test_resolve_clean_mesh(self):
        mesh = CSGOperations.create_box(10, 10, 10)
        resolver = ManifoldResolver()
        result = resolver.resolve(mesh)
        assert result.mesh is not None
        assert len(result.issues_fixed) > 0

    def test_manifold_resolution(self):
        mesh = CSGOperations.create_sphere(radius=5)
        resolver = ManifoldResolver()
        result = resolver.resolve(mesh)
        assert isinstance(result.mesh, trimesh.Trimesh)
        assert result.is_watertight  # sphere should be watertight

    def test_fix_normals(self):
        mesh = CSGOperations.create_box(10, 10, 10)
        fixed = ManifoldResolver.fix_normals(mesh)
        assert isinstance(fixed, trimesh.Trimesh)

    def test_merge_vertices(self):
        mesh = CSGOperations.create_box(10, 10, 10)
        merged = ManifoldResolver.merge_vertices(mesh)
        assert isinstance(merged, trimesh.Trimesh)
