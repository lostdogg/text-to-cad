"""NLP Agent: converts natural language text into a GeometrySpec.

Uses rule-based parsing by default; optionally uses OpenAI GPT-4 when an
OPENAI_API_KEY is configured.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.geometry import (
    BooleanOpSpec,
    BooleanOpType,
    GeometrySpec,
    PrimitiveSpec,
    PrimitiveType,
    Transform,
    Vector3,
)

logger = logging.getLogger(__name__)

# Unit conversion to mm
UNIT_FACTORS: Dict[str, float] = {
    "mm": 1.0,
    "cm": 10.0,
    "m": 1000.0,
    "in": 25.4,
    "inch": 25.4,
    "inches": 25.4,
    '"': 25.4,
}

# Dimension keywords
DIM_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:x\s*(\d+(?:\.\d+)?)\s*(?:x\s*(\d+(?:\.\d+)?))?)?(?:\s*(mm|cm|m|in|inch|inches|\"|\'))?",
    re.IGNORECASE,
)

SINGLE_DIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|cm|m|in|inch|inches|\")?",
    re.IGNORECASE,
)


class NLPAgent:
    """Parse natural language descriptions into GeometrySpec objects."""

    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key
        self._openai_available = False
        if openai_api_key:
            try:
                import openai  # noqa: F401
                self._openai_available = True
                logger.info("OpenAI integration enabled")
            except ImportError:
                logger.warning("openai package not installed; using rule-based NLP")

    async def parse_text(self, text: str) -> GeometrySpec:
        """Main entry point: parse text -> GeometrySpec."""
        text_lower = text.lower().strip()
        if self._openai_available and self.openai_api_key:
            try:
                return await self._parse_with_openai(text)
            except Exception as exc:
                logger.warning("OpenAI parse failed, falling back to rules: %s", exc)
        return self._parse_with_rules(text_lower, original=text)

    # ------------------------------------------------------------------ #
    # Rule-based parser                                                    #
    # ------------------------------------------------------------------ #

    def _parse_with_rules(self, text: str, original: str = "") -> GeometrySpec:
        primitives: List[PrimitiveSpec] = []
        operations: List[BooleanOpSpec] = []

        # Check for boolean operations first
        has_subtract = any(kw in text for kw in ["subtract", "cut", "remove", "drill", "hole", "minus"])
        has_union = any(kw in text for kw in ["union", "combine", "merge", "add", "attach"])
        has_intersect = any(kw in text for kw in ["intersect", "intersection", "overlap", "common"])

        # Split compound sentences — also split on "from" for boolean patterns like
        # "subtract cylinder FROM cube" / "cut hole FROM box"
        sentences = re.split(r"\band\b|\bthen\b|,|;|\bfrom\b", text)
        prim_idx = 0
        for sentence in sentences:
            sentence = sentence.strip()
            prim = self._extract_primitive(sentence)
            if prim is not None:
                primitives.append(prim)
                prim_idx += 1

        # If no primitives found, try the full text
        if not primitives:
            prim = self._extract_primitive(text)
            if prim:
                primitives.append(prim)

        # Build boolean operations
        if has_subtract and len(primitives) >= 2:
            operations.append(
                BooleanOpSpec(
                    operation=BooleanOpType.SUBTRACTION,
                    operand_a=0,
                    operand_b=1,
                    name="subtraction",
                )
            )
        elif has_union and len(primitives) >= 2:
            operations.append(
                BooleanOpSpec(
                    operation=BooleanOpType.UNION,
                    operand_a=0,
                    operand_b=1,
                    name="union",
                )
            )
        elif has_intersect and len(primitives) >= 2:
            operations.append(
                BooleanOpSpec(
                    operation=BooleanOpType.INTERSECTION,
                    operand_a=0,
                    operand_b=1,
                    name="intersection",
                )
            )

        # Default: if only one primitive and no operation, wrap it
        if not primitives:
            # Fallback to a 20mm cube
            logger.warning("Could not parse primitives; using default 20mm cube")
            primitives.append(
                PrimitiveSpec(
                    type=PrimitiveType.BOX,
                    dimensions={"width": 20.0, "height": 20.0, "depth": 20.0},
                )
            )

        return GeometrySpec(
            primitives=primitives,
            operations=operations,
            description=original or text,
        )

    def _extract_primitive(self, text: str) -> Optional[PrimitiveSpec]:
        """Try to extract a single primitive from text."""
        if any(kw in text for kw in ["box", "cube", "block", "rectangular", "prism", "rect"]):
            return self._parse_box(text)
        if any(kw in text for kw in ["cylinder", "tube", "pipe", "rod", "shaft"]):
            return self._parse_cylinder(text)
        if any(kw in text for kw in ["sphere", "ball", "globe"]):
            return self._parse_sphere(text)
        if any(kw in text for kw in ["cone", "pyramid", "taper"]):
            return self._parse_cone(text)
        if any(kw in text for kw in ["torus", "ring", "donut", "doughnut"]):
            return self._parse_torus(text)
        return None

    def _parse_box(self, text: str) -> PrimitiveSpec:
        dims = self._extract_three_dims(text)
        w = dims[0] if len(dims) > 0 else 20.0
        h = dims[1] if len(dims) > 1 else w
        d = dims[2] if len(dims) > 2 else h
        return PrimitiveSpec(
            type=PrimitiveType.BOX,
            dimensions={"width": w, "height": h, "depth": d},
            name="box",
        )

    def _parse_cylinder(self, text: str) -> PrimitiveSpec:
        dims = self._extract_dims(text)
        radius = dims[0] / 2.0 if dims else 5.0
        if "radius" in text or "r=" in text:
            radius = dims[0] if dims else 5.0
        height = dims[1] if len(dims) > 1 else radius * 4
        # Check for "diameter X height Y" pattern
        dia_match = re.search(r"diameter\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if dia_match:
            radius = float(dia_match.group(1)) / 2.0
        h_match = re.search(r"height\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if h_match:
            height = self._to_mm(float(h_match.group(1)), self._find_unit(text))
        return PrimitiveSpec(
            type=PrimitiveType.CYLINDER,
            dimensions={"radius": radius, "height": height},
            name="cylinder",
        )

    def _parse_sphere(self, text: str) -> PrimitiveSpec:
        dims = self._extract_dims(text)
        radius = dims[0] / 2.0 if dims else 10.0
        if "radius" in text:
            radius = dims[0] if dims else 10.0
        return PrimitiveSpec(
            type=PrimitiveType.SPHERE,
            dimensions={"radius": radius},
            name="sphere",
        )

    def _parse_cone(self, text: str) -> PrimitiveSpec:
        dims = self._extract_dims(text)
        radius = dims[0] / 2.0 if dims else 10.0
        height = dims[1] if len(dims) > 1 else radius * 2
        return PrimitiveSpec(
            type=PrimitiveType.CONE,
            dimensions={"radius": radius, "height": height},
            name="cone",
        )

    def _parse_torus(self, text: str) -> PrimitiveSpec:
        dims = self._extract_dims(text)
        major_r = dims[0] if dims else 15.0
        minor_r = dims[1] if len(dims) > 1 else major_r * 0.25
        return PrimitiveSpec(
            type=PrimitiveType.TORUS,
            dimensions={"major_radius": major_r, "minor_radius": minor_r},
            name="torus",
        )

    # ------------------------------------------------------------------ #
    # Dimension extraction helpers                                         #
    # ------------------------------------------------------------------ #

    def _extract_three_dims(self, text: str) -> List[float]:
        """Extract up to three dimensions from 'NxNxN unit' patterns."""
        unit = self._find_unit(text)
        # Try NxNxN
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)",
            text,
        )
        if m:
            return [self._to_mm(float(m.group(i)), unit) for i in (1, 2, 3)]
        # Try NxN
        m = re.search(r"(\d+(?:\.\d+)?)\s*[xX\*]\s*(\d+(?:\.\d+)?)", text)
        if m:
            v1 = self._to_mm(float(m.group(1)), unit)
            v2 = self._to_mm(float(m.group(2)), unit)
            return [v1, v2, v2]
        return self._extract_dims(text)

    def _extract_dims(self, text: str) -> List[float]:
        """Extract individual dimension values from text."""
        unit = self._find_unit(text)
        numbers = re.findall(r"\d+(?:\.\d+)?", text)
        # Filter out obviously non-dimension numbers (e.g. year-like)
        result = []
        for n in numbers:
            val = float(n)
            if 0.01 <= val <= 10000:
                result.append(self._to_mm(val, unit))
        return result[:3]

    @staticmethod
    def _find_unit(text: str) -> str:
        for unit in ["inches", "inch", "in", "cm", "mm", "m"]:
            if unit in text:
                return unit
        return "mm"

    @staticmethod
    def _to_mm(value: float, unit: str) -> float:
        factor = UNIT_FACTORS.get(unit.lower(), 1.0)
        return round(value * factor, 4)

    # ------------------------------------------------------------------ #
    # OpenAI integration                                                   #
    # ------------------------------------------------------------------ #

    async def _parse_with_openai(self, text: str) -> GeometrySpec:
        """Use GPT-4 to parse the natural language description."""
        import openai

        prompt = f"""You are a CAD geometry parser. Given a natural language description of a 3D object,
return a JSON object with this exact structure:
{{
  "primitives": [
    {{
      "type": "box|cylinder|sphere|cone|torus",
      "dimensions": {{"width": N, "height": N, "depth": N}},
      "name": "optional name"
    }}
  ],
  "operations": [
    {{
      "operation": "union|intersection|subtraction",
      "operand_a": 0,
      "operand_b": 1,
      "name": "optional"
    }}
  ],
  "description": "original text"
}}
All dimensions must be in millimeters.

User description: {text}

JSON only, no markdown:"""

        client = openai.AsyncOpenAI(api_key=self.openai_api_key)
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        raw = response.choices[0].message.content.strip()
        data = json.loads(raw)
        primitives = [PrimitiveSpec(**p) for p in data.get("primitives", [])]
        operations = [BooleanOpSpec(**o) for o in data.get("operations", [])]
        return GeometrySpec(
            primitives=primitives,
            operations=operations,
            description=data.get("description", text),
        )
