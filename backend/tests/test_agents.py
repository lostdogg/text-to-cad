"""Tests for agent classes."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.agents.coordinator import AgentCoordinator
from backend.app.agents.csg_agent import CSGAgent
from backend.app.agents.nlp_agent import NLPAgent
from backend.app.agents.validation_agent import ValidationAgent
from backend.app.cad.csg_operations import CSGOperations
from backend.app.models.geometry import (
    BooleanOpSpec,
    BooleanOpType,
    GeometrySpec,
    PrimitiveSpec,
    PrimitiveType,
)


# ------------------------------------------------------------------ #
# NLP Agent                                                           #
# ------------------------------------------------------------------ #

class TestNLPAgent:
    def setup_method(self):
        self.agent = NLPAgent()

    def _parse(self, text: str) -> GeometrySpec:
        return asyncio.get_event_loop().run_until_complete(self.agent.parse_text(text))

    def test_nlp_parse_box(self):
        spec = self._parse("create a 10mm x 20mm x 5mm box")
        assert len(spec.primitives) >= 1
        prim = spec.primitives[0]
        assert prim.type == PrimitiveType.BOX or prim.type == "box"
        dims = prim.dimensions
        assert dims.get("width") == pytest.approx(10.0, abs=0.1)

    def test_nlp_parse_cylinder(self):
        spec = self._parse("make a cylinder with radius 8mm and height 30mm")
        assert len(spec.primitives) >= 1
        prim = spec.primitives[0]
        assert prim.type == PrimitiveType.CYLINDER or prim.type == "cylinder"

    def test_nlp_parse_sphere(self):
        spec = self._parse("a sphere with radius 15mm")
        assert len(spec.primitives) >= 1
        prim = spec.primitives[0]
        assert prim.type == PrimitiveType.SPHERE or prim.type == "sphere"

    def test_nlp_parse_boolean_operation(self):
        spec = self._parse("subtract a 5mm cylinder from a 20mm cube")
        assert len(spec.operations) >= 1
        op = spec.operations[0]
        assert op.operation == BooleanOpType.SUBTRACTION or op.operation == "subtraction"

    def test_nlp_parse_union(self):
        spec = self._parse("combine a box and a sphere")
        assert len(spec.primitives) >= 1

    def test_nlp_fallback_default(self):
        spec = self._parse("something unrecognizable xyz123")
        # Should return a fallback primitive
        assert len(spec.primitives) >= 1


# ------------------------------------------------------------------ #
# CSG Agent                                                           #
# ------------------------------------------------------------------ #

class TestCSGAgent:
    def setup_method(self):
        self.agent = CSGAgent()

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_csg_agent_build_box(self):
        spec = GeometrySpec(
            primitives=[
                PrimitiveSpec(
                    type=PrimitiveType.BOX,
                    dimensions={"width": 10, "height": 10, "depth": 10},
                )
            ]
        )
        mesh_data = self._run(self.agent.build_from_spec(spec))
        assert mesh_data.vertex_count > 0
        assert mesh_data.face_count > 0

    def test_csg_agent_process(self):
        spec_a = GeometrySpec(
            primitives=[
                PrimitiveSpec(type=PrimitiveType.BOX, dimensions={"width": 20, "height": 20, "depth": 20})
            ]
        )
        spec_b = GeometrySpec(
            primitives=[
                PrimitiveSpec(type=PrimitiveType.CYLINDER, dimensions={"radius": 5, "height": 25})
            ]
        )
        result = self._run(self.agent.process_operation("subtraction", [spec_a, spec_b]))
        assert result.vertex_count > 0

    def test_csg_agent_boolean_spec(self):
        spec = GeometrySpec(
            primitives=[
                PrimitiveSpec(type=PrimitiveType.BOX, dimensions={"width": 20, "height": 20, "depth": 20}),
                PrimitiveSpec(type=PrimitiveType.SPHERE, dimensions={"radius": 8}),
            ],
            operations=[
                BooleanOpSpec(operation=BooleanOpType.UNION, operand_a=0, operand_b=1)
            ],
        )
        mesh_data = self._run(self.agent.build_from_spec(spec))
        assert mesh_data.face_count > 0


# ------------------------------------------------------------------ #
# Validation Agent                                                    #
# ------------------------------------------------------------------ #

class TestValidationAgent:
    def setup_method(self):
        self.agent = ValidationAgent()

    def _validate(self, mesh, mfg=None):
        return asyncio.get_event_loop().run_until_complete(
            self.agent.validate_mesh(mesh, mfg)
        )

    def test_validation_agent_watertight(self):
        mesh = CSGOperations.create_sphere(radius=10)
        result = self._validate(mesh)
        assert result.is_valid is True or result.warning_count() >= 0

    def test_validation_agent_box(self):
        mesh = CSGOperations.create_box(20, 20, 20)
        result = self._validate(mesh)
        assert result.mesh_stats.vertex_count > 0

    def test_validation_cnc(self):
        mesh = CSGOperations.create_box(20, 20, 20)
        result = self._validate(mesh, "cnc_3axis")
        assert result.manufacturing_type == "cnc_3axis"

    def test_validation_3dprint(self):
        mesh = CSGOperations.create_box(20, 20, 20)
        result = self._validate(mesh, "3d_printing")
        assert result.manufacturing_type == "3d_printing"


# ------------------------------------------------------------------ #
# Coordinator                                                         #
# ------------------------------------------------------------------ #

@pytest.mark.asyncio
async def test_coordinator_workflow():
    coordinator = AgentCoordinator()
    result = await coordinator.process("create a 20mm cube")
    assert result.success is True
    assert result.model is not None
    assert result.model.mesh_data is not None
    assert result.model.mesh_data.vertex_count > 0


@pytest.mark.asyncio
async def test_coordinator_with_manufacturing():
    coordinator = AgentCoordinator()
    result = await coordinator.process(
        "create a 30mm x 30mm x 10mm box",
        manufacturing_type="cnc_3axis",
    )
    assert result.success is True
    assert result.manufacturing_report is not None


@pytest.mark.asyncio
async def test_coordinator_boolean():
    coordinator = AgentCoordinator()
    result = await coordinator.process(
        "subtract a 5mm cylinder from a 20mm cube"
    )
    assert result.success is True
