"""Deterministic tests for non-UI static CAD/CAM libs."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backend.app.cad.csg_operations import CSGOperations
from backend.app.cad.exporter import CADExporter
from backend.app.manufacturing.cnc import CNCOptimizer
from backend.app.models.geometry import MeshData
from backend.app.models.manufacturing import CNCParams, LaserParams, PrintParams


def test_mesh_serialization_roundtrip_deterministic():
    mesh = CSGOperations.create_box(10, 20, 5)
    first = MeshData.from_trimesh(mesh)
    second = MeshData.from_trimesh(first.to_trimesh())

    assert second.vertex_count == first.vertex_count
    assert second.face_count == first.face_count
    assert second.vertices == first.vertices
    assert second.faces == first.faces


def test_cnc_estimation_is_deterministic_for_same_input():
    mesh = CSGOperations.create_box(30, 30, 10)
    params = CNCParams(material="aluminum")
    opt = CNCOptimizer()

    first_cost = opt.estimate_cost(mesh, params)
    second_cost = opt.estimate_cost(mesh, params)
    first_time = opt.estimate_time(mesh, params)
    second_time = opt.estimate_time(mesh, params)

    assert first_cost.total_cost == second_cost.total_cost
    assert first_time.total_time == second_time.total_time


def test_export_gcode_3dprint_is_deterministic():
    mesh = CSGOperations.create_box(20, 20, 10)
    params = PrintParams()

    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "print1.gcode"
        p2 = Path(tmp) / "print2.gcode"
        CADExporter.export_gcode_3dprint(mesh, str(p1), params)
        CADExporter.export_gcode_3dprint(mesh, str(p2), params)
        assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")


def test_export_gcode_cnc_is_deterministic():
    mesh = CSGOperations.create_box(40, 25, 8)
    params = CNCParams()

    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "cnc1.gcode"
        p2 = Path(tmp) / "cnc2.gcode"
        CADExporter.export_gcode_cnc(mesh, str(p1), params)
        CADExporter.export_gcode_cnc(mesh, str(p2), params)
        assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")


def test_export_gcode_laser_is_deterministic():
    mesh = CSGOperations.create_box(100, 50, 3)
    profile = [[0, 0], [100, 0], [100, 50], [0, 50], [0, 0]]
    params = LaserParams()

    with tempfile.TemporaryDirectory() as tmp:
        p1 = Path(tmp) / "laser1.gcode"
        p2 = Path(tmp) / "laser2.gcode"
        CADExporter.export_gcode_laser(profile, str(p1), params)
        CADExporter.export_gcode_laser(profile, str(p2), params)
        assert p1.read_text(encoding="utf-8") == p2.read_text(encoding="utf-8")
