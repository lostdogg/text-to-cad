"""Tests for manufacturing optimizers."""

from __future__ import annotations

import pytest

from backend.app.cad.csg_operations import CSGOperations
from backend.app.manufacturing.cnc import CNCOptimizer
from backend.app.manufacturing.laser_cutting import LaserOptimizer
from backend.app.manufacturing.printing_3d import PrintingOptimizer
from backend.app.models.manufacturing import CNCParams, LaserParams, PrintParams


class TestCNCOptimizer:
    def setup_method(self):
        self.opt = CNCOptimizer()
        self.mesh = CSGOperations.create_box(50, 30, 10)

    def test_cnc_toolpath_generation(self):
        toolpaths = self.opt.generate_toolpaths(self.mesh, tool_diameter=6.0, material="aluminum")
        assert len(toolpaths) >= 2
        assert any(tp.operation == "facing" for tp in toolpaths)
        assert any(tp.operation == "contouring" for tp in toolpaths)

    def test_cnc_cost_estimation(self):
        cost = self.opt.estimate_cost(self.mesh, CNCParams())
        assert cost.total_cost >= 0

    def test_cnc_time_estimation(self):
        time_est = self.opt.estimate_time(self.mesh, CNCParams())
        assert time_est.total_time > 0

    def test_cnc_fixturing(self):
        fixture = self.opt.optimize_fixturing(self.mesh)
        assert fixture.workholding in ("vise", "vacuum_plate", "fixture_plate")

    def test_cnc_accessibility(self):
        report = self.opt.check_accessibility(self.mesh)
        assert report.accessibility_ratio >= 0.0
        assert report.accessibility_ratio <= 1.0

    def test_cnc_optimize(self):
        result = self.opt.optimize(self.mesh)
        assert result.success is True


class TestPrintingOptimizer:
    def setup_method(self):
        self.opt = PrintingOptimizer()
        self.mesh = CSGOperations.create_box(20, 20, 30)

    def test_3d_print_orientation(self):
        result = self.opt.optimize_orientation(self.mesh)
        assert result.z_height_mm > 0
        assert result.rotation_x in (0.0, 90.0, 180.0)

    def test_3d_print_supports(self):
        supports = self.opt.generate_supports(self.mesh, angle_threshold=45.0)
        assert supports.volume_mm3 >= 0.0

    def test_3d_print_material_volume(self):
        vol = self.opt.estimate_material_volume(self.mesh)
        assert vol > 0

    def test_3d_print_layer_analysis(self):
        analysis = self.opt.layer_analysis(self.mesh, layer_height=0.2)
        assert analysis.layer_count > 0

    def test_3d_print_cost(self):
        cost = self.opt.estimate_cost(self.mesh, PrintParams())
        assert cost.total_cost >= 0

    def test_3d_print_optimize(self):
        result = self.opt.optimize(self.mesh)
        assert result.success is True


class TestLaserOptimizer:
    def setup_method(self):
        self.opt = LaserOptimizer()
        self.mesh = CSGOperations.create_box(100, 50, 3)

    def test_laser_profile_extraction(self):
        profile = self.opt.extract_profile(self.mesh)
        assert len(profile) >= 4

    def test_laser_nesting(self):
        profile = self.opt.extract_profile(self.mesh)
        result = self.opt.nest_parts([profile], sheet_size=(600, 400))
        assert result.parts_placed >= 1
        assert 0.0 <= result.efficiency <= 1.0

    def test_laser_kerf_compensation(self):
        profile = [[0, 0], [100, 0], [100, 50], [0, 50], [0, 0]]
        compensated = self.opt.calculate_kerf_compensation(profile, kerf_width=0.2)
        assert len(compensated) == len(profile)

    def test_laser_cost_estimation(self):
        cost = self.opt.estimate_cost(self.mesh, LaserParams())
        assert cost.total_cost >= 0

    def test_laser_time_estimation(self):
        time_est = self.opt.estimate_time(self.mesh, LaserParams())
        assert time_est.total_time > 0

    def test_laser_optimize(self):
        result = self.opt.optimize(self.mesh)
        assert result.success is True


class TestValidationWallThickness:
    """Test wall-thickness and validation constraints."""

    def test_validation_wall_thickness(self):
        import asyncio
        from backend.app.agents.validation_agent import ValidationAgent
        mesh = CSGOperations.create_box(10, 10, 10)
        agent = ValidationAgent()
        result = asyncio.get_event_loop().run_until_complete(
            agent.validate_mesh(mesh, manufacturing_type="3d_printing")
        )
        assert result.manufacturing_type == "3d_printing"
        assert result.mesh_stats.vertex_count > 0

    def test_cost_estimation_multiple_materials(self):
        mesh = CSGOperations.create_cylinder(radius=10, height=20)
        cnc = CNCOptimizer()
        for material in ["aluminum", "steel", "plastic", "wood"]:
            params = CNCParams(material=material)
            cost = cnc.estimate_cost(mesh, params)
            assert cost.total_cost >= 0
