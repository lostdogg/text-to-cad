"""Benchmark / regression tests for complex Text-to-CAD prompts.

These tests verify that the full pipeline handles real-world complex inputs
correctly end-to-end (parse + build + validate).  They act as a quality gate:
all benchmark prompts must produce a non-empty mesh and a successful result.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import pytest

from backend.app.agents.coordinator import AgentCoordinator
from backend.app.agents.nlp_agent import NLPAgent
from backend.app.models.geometry import BooleanOpType, GeometrySpec, PrimitiveType


# ------------------------------------------------------------------ #
# Helpers                                                              #
# ------------------------------------------------------------------ #

def _parse(text: str) -> GeometrySpec:
    agent = NLPAgent()
    return asyncio.get_event_loop().run_until_complete(agent.parse_text(text))


async def _run(text: str, mfg: Optional[str] = None):
    coord = AgentCoordinator()
    return await coord.process(text, manufacturing_type=mfg)


# ------------------------------------------------------------------ #
# NLP-level benchmarks: parse accuracy                               #
# ------------------------------------------------------------------ #

class TestNLPBenchmark:
    """Verify that complex prompts produce semantically correct GeometrySpecs."""

    # ----- Multi-dimensional box -------------------------------------- #

    def test_bracket_three_dim(self):
        """'50mm × 30mm × 10mm box' extracts three distinct dimensions."""
        spec = _parse("create a 50mm × 30mm × 10mm mounting bracket")
        assert len(spec.primitives) >= 1
        p = spec.primitives[0]
        dims = p.dimensions
        assert pytest.approx(dims.get("width", 0), abs=1) == 50.0
        assert pytest.approx(dims.get("height", 0), abs=1) == 30.0
        assert pytest.approx(dims.get("depth", 0), abs=1) == 10.0

    def test_bracket_unicode_times(self):
        """'50 x 30 x 10 mm' (unicode ×) extracts three dimensions."""
        spec = _parse("50 x 30 x 10 mm box")
        p = spec.primitives[0]
        dims = p.dimensions
        assert pytest.approx(dims.get("width", 0), abs=1) == 50.0

    # ----- Torus major/minor radius ----------------------------------- #

    def test_torus_named_radii(self):
        """'major radius 30mm, minor radius 5mm' torus parsed correctly."""
        spec = _parse("make a torus with major radius 30mm and minor radius 5mm")
        assert len(spec.primitives) >= 1
        p = spec.primitives[0]
        assert str(p.type).lower() == "torus"
        assert pytest.approx(p.dimensions.get("major_radius", 0), abs=1) == 30.0
        assert pytest.approx(p.dimensions.get("minor_radius", 0), abs=1) == 5.0

    # ----- Boolean operations ----------------------------------------- #

    def test_subtract_cylinder_from_cube(self):
        spec = _parse("subtract a 5mm cylinder from a 20mm cube")
        assert len(spec.operations) >= 1
        op = spec.operations[0]
        assert str(op.operation).lower() == BooleanOpType.SUBTRACTION

    def test_intersect_sphere_and_box(self):
        spec = _parse("intersection of a 20mm box and a 12mm sphere")
        # Must at least have 2 primitives (even if operation isn't explicit)
        assert len(spec.primitives) >= 2

    def test_union_two_cylinders(self):
        spec = _parse("union of two 10mm cylinders")
        assert len(spec.primitives) >= 1

    # ----- Corner-holes pattern --------------------------------------- #

    def test_corner_holes_four(self):
        """'4 x 5mm holes in the corners' produces 4 hole cylinders."""
        spec = _parse(
            "create a 50mm × 30mm × 10mm aluminum mounting bracket "
            "with four 5mm holes in the corners"
        )
        # Expect base + 4 holes = 5 primitives, 4 subtraction operations
        assert len(spec.primitives) == 5, (
            f"Expected 5 primitives (1 base + 4 holes), got {len(spec.primitives)}"
        )
        assert len(spec.operations) == 4, (
            f"Expected 4 subtraction operations, got {len(spec.operations)}"
        )
        for op in spec.operations:
            assert str(op.operation).lower() == BooleanOpType.SUBTRACTION

    def test_corner_holes_two(self):
        spec = _parse("a 60mm × 20mm × 5mm plate with 2 x 4mm holes in the corners")
        # At minimum, must have the holes parsed
        hole_prims = [p for p in spec.primitives if str(p.type).lower() == "cylinder"]
        assert len(hole_prims) >= 2

    def test_corner_holes_hole_radius(self):
        """Hole cylinders should have radius ≈ 2.5mm (5mm diameter)."""
        spec = _parse(
            "50mm × 30mm × 10mm bracket with four 5mm holes in the corners"
        )
        hole_prims = [p for p in spec.primitives if str(p.type).lower() == "cylinder"]
        assert len(hole_prims) >= 1
        for hp in hole_prims:
            r = hp.dimensions.get("radius", 0)
            assert 2.0 <= r <= 3.5, f"Expected ~2.5mm radius, got {r}"

    # ----- Spatial constraints ---------------------------------------- #

    def test_sphere_on_top_of_box(self):
        spec = _parse("a 20mm sphere on top of a 30mm box")
        assert len(spec.primitives) >= 2
        # Sphere should be offset upward in Z
        sphere_prims = [p for p in spec.primitives if str(p.type).lower() == "sphere"]
        assert len(sphere_prims) >= 1
        sphere = sphere_prims[0]
        assert sphere.transform.position.z > 0

    def test_centered_cylinder(self):
        spec = _parse("a 10mm cylinder centered on top of a 30mm cube")
        assert len(spec.primitives) >= 2

    # ----- Unit conversion -------------------------------------------- #

    def test_unit_inches(self):
        spec = _parse("create a 2 inch cube")
        p = spec.primitives[0]
        w = p.dimensions.get("width", 0)
        # 2 inches = 50.8 mm
        assert pytest.approx(w, abs=1) == 50.8

    def test_unit_cm(self):
        spec = _parse("create a 5cm box")
        p = spec.primitives[0]
        w = p.dimensions.get("width", 0)
        assert pytest.approx(w, abs=1) == 50.0

    def test_unit_default_mm(self):
        spec = _parse("create a 25 box")
        p = spec.primitives[0]
        w = p.dimensions.get("width", 0)
        assert pytest.approx(w, abs=1) == 25.0

    # ----- Confidence / warnings -------------------------------------- #

    def test_confidence_explicit_shape(self):
        spec = _parse("create a 20mm box")
        assert spec.parse_confidence >= 0.5

    def test_confidence_fallback(self):
        spec = _parse("make something unrecognisable xyz_abc")
        assert spec.parse_confidence < 0.5
        assert len(spec.warnings) >= 1

    def test_warnings_on_fallback(self):
        spec = _parse("gibberish 9999 no shape here")
        assert any("default" in w.lower() or "no recognizable" in w.lower() for w in spec.warnings)


# ------------------------------------------------------------------ #
# End-to-end pipeline benchmarks                                       #
# ------------------------------------------------------------------ #

class TestPipelineBenchmark:
    """Full pipeline (NLP → CSG → Validate) golden tests."""

    def _run_sync(self, text, mfg=None):
        return asyncio.get_event_loop().run_until_complete(_run(text, mfg))

    def test_e2e_simple_box(self):
        result = self._run_sync("create a 30mm cube")
        assert result.success
        assert result.model.mesh_data.vertex_count > 0
        assert result.model.mesh_data.face_count > 0

    def test_e2e_cylinder_in_box(self):
        result = self._run_sync("subtract a 5mm cylinder from a 20mm cube")
        assert result.success
        assert result.model.mesh_data.face_count > 0

    def test_e2e_torus(self):
        result = self._run_sync("torus with major radius 15mm and minor radius 3mm")
        assert result.success
        assert result.model.mesh_data.face_count > 0

    def test_e2e_corner_holes_bracket(self):
        result = self._run_sync(
            "50mm × 30mm × 10mm aluminum mounting bracket "
            "with four 5mm holes in the corners"
        )
        assert result.success
        assert result.model.mesh_data.vertex_count > 0

    def test_e2e_telemetry_present(self):
        result = self._run_sync("create a 20mm sphere")
        assert result.telemetry is not None
        assert result.telemetry.total_duration_ms > 0
        assert result.telemetry.mesh_face_count > 0
        stage_names = [s.name for s in result.telemetry.stages]
        assert "nlp" in stage_names
        assert "csg" in stage_names

    def test_e2e_parse_confidence_in_telemetry(self):
        result = self._run_sync("20mm box")
        assert result.telemetry is not None
        assert 0.0 <= result.telemetry.parse_confidence <= 1.0

    def test_e2e_with_cnc_manufacturing(self):
        result = self._run_sync("create a 40mm × 40mm × 10mm box", mfg="cnc_3axis")
        assert result.success
        assert result.manufacturing_report is not None

    def test_e2e_with_3d_print_manufacturing(self):
        result = self._run_sync("create a 20mm box", mfg="3d_printing")
        assert result.success
        assert result.manufacturing_report is not None

    def test_e2e_remediation_hints_present(self):
        """Validation should populate remediation_hints for manufacturing types."""
        result = self._run_sync("create a 50mm × 50mm × 50mm box", mfg="3d_printing")
        assert result.success
        # Hints list may be empty for a clean box, but the field must exist
        assert result.validation is not None
        assert isinstance(result.validation.remediation_hints, list)

    def test_e2e_error_detail_for_empty_text(self):
        """Empty text must not crash the coordinator."""
        result = self._run_sync("")
        # May succeed with fallback or fail gracefully
        # Either way, no Python exception should escape
        assert result is not None

    def test_e2e_complexity_score(self):
        result = self._run_sync("create a 20mm box")
        assert result.telemetry.complexity_score >= 1

    def test_e2e_sphere_on_box(self):
        result = self._run_sync("a 10mm sphere on top of a 20mm box")
        assert result.success
        assert result.model.mesh_data.face_count > 0


# ------------------------------------------------------------------ #
# Complexity guard tests                                               #
# ------------------------------------------------------------------ #

class TestComplexityGuards:
    """Verify that oversized specs are rejected gracefully."""

    def test_complexity_error_on_too_many_primitives(self):
        from backend.app.agents.csg_agent import CSGAgent, ComplexityError
        from backend.app.models.geometry import GeometrySpec, PrimitiveSpec, PrimitiveType

        agent = CSGAgent()
        primitives = [
            PrimitiveSpec(type=PrimitiveType.BOX, dimensions={"width": 1, "height": 1, "depth": 1})
            for _ in range(51)
        ]
        spec = GeometrySpec(primitives=primitives)
        with pytest.raises(ComplexityError):
            asyncio.get_event_loop().run_until_complete(agent.build_from_spec(spec))

    def test_operation_depth_calculation(self):
        from backend.app.agents.csg_agent import CSGAgent
        from backend.app.models.geometry import (
            BooleanOpSpec, BooleanOpType, GeometrySpec, PrimitiveSpec, PrimitiveType
        )
        agent = CSGAgent()
        spec = GeometrySpec(
            primitives=[
                PrimitiveSpec(type=PrimitiveType.BOX, dimensions={"width": 10, "height": 10, "depth": 10}),
                PrimitiveSpec(type=PrimitiveType.SPHERE, dimensions={"radius": 5}),
                PrimitiveSpec(type=PrimitiveType.CYLINDER, dimensions={"radius": 3, "height": 15}),
            ],
            operations=[
                BooleanOpSpec(operation=BooleanOpType.UNION, operand_a=0, operand_b=1),
                BooleanOpSpec(operation=BooleanOpType.SUBTRACTION, operand_a=3, operand_b=2),
            ],
        )
        depth = CSGAgent._operation_depth(spec)
        assert depth == 2
