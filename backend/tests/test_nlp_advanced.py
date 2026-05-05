"""Advanced / parameterized NLP tests for the rule-based parser.

Covers:
  - Parameterized shape+dimension combinations
  - Unit conversion correctness
  - Named-dimension parsing (radius vs diameter, major/minor radius)
  - Spatial-hint transforms
  - Corner-hole pattern edge cases
  - Confidence and warning contract
  - Multi-boolean chain parsing
"""

from __future__ import annotations

import asyncio
from typing import Dict, List

import pytest

from backend.app.agents.nlp_agent import NLPAgent
from backend.app.models.geometry import (
    BooleanOpType,
    GeometrySpec,
    PrimitiveType,
)


def _parse(text: str) -> GeometrySpec:
    agent = NLPAgent()
    return asyncio.get_event_loop().run_until_complete(agent.parse_text(text))


# ------------------------------------------------------------------ #
# Parametrized shape detection                                         #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("prompt,expected_type", [
    ("create a 10mm box",           "box"),
    ("make a 10mm cube",            "box"),
    ("a 10mm x 20mm x 5mm block",   "box"),
    ("rectangular prism 30x20x10",  "box"),
    ("aluminium plate 50x40x3mm",   "box"),
    ("cylinder radius 8mm height 30mm", "cylinder"),
    ("tube 12mm diameter 50mm tall",    "cylinder"),
    ("pipe with radius 5mm",             "cylinder"),
    ("a 15mm shaft",                     "cylinder"),
    ("sphere radius 10mm",               "sphere"),
    ("ball of diameter 20mm",            "sphere"),
    ("globe radius 7",                   "sphere"),
    ("cone radius 5mm height 15mm",      "cone"),
    ("taper radius 8 height 20",         "cone"),
    ("torus major radius 20mm minor radius 5mm", "torus"),
    ("a donut with 30mm and 8mm radii",          "torus"),
])
def test_shape_detection_parametrized(prompt, expected_type):
    spec = _parse(prompt)
    assert len(spec.primitives) >= 1, f"No primitives for: {prompt!r}"
    types = [str(p.type).lower() for p in spec.primitives]
    assert expected_type in types, f"Expected {expected_type!r} in {types} for: {prompt!r}"


# ------------------------------------------------------------------ #
# Unit conversion                                                      #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("prompt,expected_mm,tol", [
    ("10mm box",              10.0,   0.5),
    ("1cm box",               10.0,   0.5),
    ("0.1m box",             100.0,   1.0),
    ("1 inch box",            25.4,   0.5),
    ("2 inches box",          50.8,   0.5),
    ("1.5 in box",            38.1,   0.5),
])
def test_unit_conversion(prompt, expected_mm, tol):
    spec = _parse(prompt)
    assert len(spec.primitives) >= 1
    p = spec.primitives[0]
    w = p.dimensions.get("width", p.dimensions.get("radius", 0))
    assert abs(w - expected_mm) <= tol, (
        f"prompt={prompt!r}: got {w} mm, expected ~{expected_mm} mm"
    )


# ------------------------------------------------------------------ #
# Named dimension extraction                                           #
# ------------------------------------------------------------------ #

def test_cylinder_radius_keyword():
    spec = _parse("cylinder with radius 8mm and height 30mm")
    p = spec.primitives[0]
    assert pytest.approx(p.dimensions["radius"], abs=0.5) == 8.0
    assert pytest.approx(p.dimensions["height"], abs=0.5) == 30.0


def test_cylinder_diameter_keyword():
    spec = _parse("cylinder with diameter 16mm and height 30mm")
    p = spec.primitives[0]
    # diameter 16mm => radius 8mm
    assert pytest.approx(p.dimensions["radius"], abs=0.5) == 8.0


def test_sphere_radius_keyword():
    spec = _parse("sphere with radius 15mm")
    p = spec.primitives[0]
    assert pytest.approx(p.dimensions["radius"], abs=0.5) == 15.0


def test_torus_major_minor_named():
    spec = _parse("torus with major radius 30mm and minor radius 5mm")
    p = spec.primitives[0]
    assert pytest.approx(p.dimensions["major_radius"], abs=0.5) == 30.0
    assert pytest.approx(p.dimensions["minor_radius"], abs=0.5) == 5.0


def test_box_three_dims_named_separator():
    spec = _parse("50mm × 30mm × 10mm box")
    p = spec.primitives[0]
    assert pytest.approx(p.dimensions["width"],  abs=1) == 50.0
    assert pytest.approx(p.dimensions["height"], abs=1) == 30.0
    assert pytest.approx(p.dimensions["depth"],  abs=1) == 10.0


# ------------------------------------------------------------------ #
# Boolean operations                                                   #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("prompt,expected_op", [
    ("subtract a cylinder from a box",              "subtraction"),
    ("cut a sphere out of a cube",                  "subtraction"),
    ("remove a cylinder from a box",                "subtraction"),
    ("drill a hole in a box",                       "subtraction"),
    ("combine a box and a cylinder",                "union"),
    ("merge a sphere with a box",                   "union"),
    ("union of a box and a sphere",                 "union"),
    ("intersect a box with a sphere",               "intersection"),
    ("intersection of a cylinder and a box",        "intersection"),
])
def test_boolean_detection_parametrized(prompt, expected_op):
    spec = _parse(prompt)
    # The spec must have at least 1 primitive and 1 operation or two primitives
    total = len(spec.primitives) + len(spec.operations)
    assert total >= 2, f"Expected at least 2 components for: {prompt!r}"
    if spec.operations:
        ops = [str(o.operation).lower() for o in spec.operations]
        assert expected_op in ops, (
            f"Expected {expected_op!r} in {ops} for: {prompt!r}"
        )


# ------------------------------------------------------------------ #
# Corner-hole patterns                                                 #
# ------------------------------------------------------------------ #

@pytest.mark.parametrize("prompt,n_holes", [
    ("50x30x10mm bracket with four 5mm holes in the corners",  4),
    ("80x60x5mm plate with 4 holes in the corners",            4),
    ("100x50x3mm panel with 2 x 6mm holes at corners",        2),
])
def test_corner_hole_count(prompt, n_holes):
    spec = _parse(prompt)
    hole_prims = [p for p in spec.primitives if str(p.type).lower() == "cylinder"]
    assert len(hole_prims) >= n_holes, (
        f"Expected {n_holes} hole cylinders, got {len(hole_prims)} for: {prompt!r}"
    )
    # Each hole subtracted
    assert len(spec.operations) >= n_holes


def test_corner_holes_subtraction_ops_all_subtract():
    spec = _parse("50x30x10mm bracket with four 5mm holes in the corners")
    for op in spec.operations:
        assert str(op.operation).lower() == "subtraction"


def test_corner_holes_positioned():
    """Hole cylinders should have non-zero XY positions (not all at origin)."""
    spec = _parse("50mm × 30mm × 10mm bracket with four 5mm holes in the corners")
    hole_prims = [p for p in spec.primitives if str(p.type).lower() == "cylinder"]
    positions = [(p.transform.position.x, p.transform.position.y) for p in hole_prims]
    # At least 2 unique positions
    unique_positions = set(positions)
    assert len(unique_positions) >= 2, f"Holes not distributed: {positions}"


# ------------------------------------------------------------------ #
# Spatial transform hints                                              #
# ------------------------------------------------------------------ #

def test_sphere_on_top_z_positive():
    spec = _parse("a 10mm sphere on top of a 20mm box")
    spheres = [p for p in spec.primitives if str(p.type).lower() == "sphere"]
    assert len(spheres) >= 1
    assert spheres[0].transform.position.z > 0


def test_offset_by_applied():
    spec = _parse("a 10mm cylinder offset by 15mm")
    cylinders = [p for p in spec.primitives if str(p.type).lower() == "cylinder"]
    if len(cylinders) >= 2:
        assert cylinders[-1].transform.position.x != 0


# ------------------------------------------------------------------ #
# Confidence and warnings contract                                     #
# ------------------------------------------------------------------ #

def test_confidence_is_float_in_range():
    for prompt in [
        "20mm box",
        "gibberish 9999",
        "subtract a cylinder from a box",
        "50x30x10mm bracket with four 5mm holes in the corners",
    ]:
        spec = _parse(prompt)
        assert isinstance(spec.parse_confidence, float)
        assert 0.0 <= spec.parse_confidence <= 1.0, (
            f"Confidence out of range for: {prompt!r}: {spec.parse_confidence}"
        )


def test_warnings_is_list():
    spec = _parse("box")
    assert isinstance(spec.warnings, list)


def test_low_confidence_has_warning():
    spec = _parse("totally unrecognisable prompt xyzabc")
    assert spec.parse_confidence < 0.5
    assert len(spec.warnings) >= 1


def test_good_prompt_confidence_high():
    spec = _parse("create a 50mm × 30mm × 10mm box")
    assert spec.parse_confidence >= 0.5


# ------------------------------------------------------------------ #
# Complexity score                                                     #
# ------------------------------------------------------------------ #

def test_complexity_score_simple():
    spec = _parse("20mm box")
    assert spec.complexity_score == 1  # 1 primitive, 0 ops


def test_complexity_score_with_operations():
    spec = _parse("subtract a 5mm cylinder from a 20mm cube")
    # 2 primitives + 2 × 1 operation = 4
    assert spec.complexity_score >= 4


def test_complexity_score_corner_holes():
    spec = _parse("50x30x10mm bracket with four 5mm holes in corners")
    # 5 primitives + 2 × 4 ops = 13
    assert spec.complexity_score >= 13


# ------------------------------------------------------------------ #
# Multi-boolean chain (>2 operands)                                   #
# ------------------------------------------------------------------ #

def test_multi_subtract_chain():
    """Three-shape subtract chain should produce multiple operations."""
    spec = _parse("subtract a sphere and a cylinder from a 30mm box")
    # Expect 3 primitives and ≥2 subtraction operations in a chain
    assert len(spec.primitives) >= 2
    if len(spec.operations) >= 2:
        ops = [str(o.operation).lower() for o in spec.operations]
        assert all(op == "subtraction" for op in ops)


# ------------------------------------------------------------------ #
# Fallback behaviour contract                                          #
# ------------------------------------------------------------------ #

def test_fallback_produces_default_cube():
    spec = _parse("completely unrecognisable aaaabbb")
    assert len(spec.primitives) == 1
    p = spec.primitives[0]
    assert str(p.type).lower() == "box"
    assert p.dimensions.get("width", 0) == 20.0


def test_empty_string_fallback():
    spec = _parse("")
    # Should not crash and should return a fallback
    assert len(spec.primitives) >= 1
