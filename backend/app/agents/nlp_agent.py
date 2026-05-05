"""NLP Agent: converts natural language text into a GeometrySpec.

Uses rule-based parsing by default; optionally delegates to an AI provider
(OpenAI, Anthropic, Google Gemini, Ollama, or any OpenAI-compatible API)
when an :class:`~backend.app.models.ai_provider.AIProviderConfig` is supplied.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from ..models.ai_provider import AIProvider, AIProviderConfig, PROVIDER_DEFAULT_MODELS
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

# System prompt for AI providers: separates instructions from user content (best practice)
_SYSTEM_PROMPT = """\
You are a precise CAD geometry parser. Given a natural language description of a \
3D object, return ONLY a valid JSON object with this exact structure:
{
  "primitives": [
    {
      "type": "box|cylinder|sphere|cone|torus",
      "dimensions": {"width": N, "height": N, "depth": N},
      "transform": {
        "position": {"x": 0, "y": 0, "z": 0},
        "rotation": {"x": 0, "y": 0, "z": 0},
        "scale": {"x": 1, "y": 1, "z": 1}
      },
      "name": "optional name"
    }
  ],
  "operations": [
    {
      "operation": "union|intersection|subtraction",
      "operand_a": 0,
      "operand_b": 1,
      "name": "optional"
    }
  ],
  "description": "original text"
}
Rules:
- All dimensions must be in millimeters.
- Use position/rotation/scale in transform when spatial relationships are described \
(e.g. "on top of", "offset by", "rotated 45 degrees").
- For patterns like "4 holes at corners", create 4 primitives positioned at the \
corners of the base shape.
- Do NOT include markdown, code fences, or any text outside the JSON object.\
"""

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

# Corner-hole pattern: "4 5mm holes in the corners" or "four 5mm diameter holes at corners"
_CORNER_HOLES_RE = re.compile(
    r"(\d+|four|three|two|six|eight)\s+(?:x\s+)?(\d+(?:\.\d+)?)\s*(?:mm|cm)?\s*"
    r"(?:diameter\s+|dia\.?\s+|radius\s+)?(?:holes?|bores?|through[- ]holes?|counterbores?)\s*"
    r"(?:in|at|on|through)?\s*(?:the\s+)?(?:corners?|edges?|sides?)",
    re.IGNORECASE,
)

# Dimensionless variant: "4 holes in the corners" (no explicit hole size)
_CORNER_HOLES_NO_DIM_RE = re.compile(
    r"(\d+|four|three|two|six|eight)\s+"
    r"(?:holes?|bores?|through[- ]holes?)\s*"
    r"(?:in|at|on)?\s*(?:the\s+)?(?:corners?|edges?)",
    re.IGNORECASE,
)

# "N holes" fallback (no corner/positional qualifier) – weaker match
_N_HOLES_RE = re.compile(
    r"(\d+|four|three|two|six|eight)\s+(?:x\s+)?(\d+(?:\.\d+)?)\s*(?:mm|cm)?\s*"
    r"(?:diameter\s+|dia\.?\s+)?(?:holes?|bores?)",
    re.IGNORECASE,
)

# Named-word numbers
_WORD_TO_NUM: Dict[str, int] = {
    "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

# Spatial relationship keywords
_SPATIAL_ON_TOP = re.compile(r"\bon\s+top\s+of\b|\babove\b|\bon\s+top\b", re.IGNORECASE)
_SPATIAL_BELOW = re.compile(r"\bbelow\b|\bunder\b|\bunderneath\b", re.IGNORECASE)
_SPATIAL_CENTERED = re.compile(r"\bcentered?\b|\bin\s+the\s+cent(?:er|re)\b|\bmiddle\b", re.IGNORECASE)
_SPATIAL_OFFSET = re.compile(
    r"offset\s+by\s+(\d+(?:\.\d+)?)\s*(mm|cm|m|in)?", re.IGNORECASE
)
_ROTATION_RE = re.compile(
    r"rotated?\s+(\d+(?:\.\d+)?)\s*(?:degrees?|deg|°)?\s*(?:about|around|along)?\s*([xXyYzZ])?",
    re.IGNORECASE,
)


def _strip_json_fences(raw: str) -> str:
    """Remove markdown code fences that some models wrap around JSON output."""
    raw = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _build_geometry_spec_from_dict(data: dict, original_text: str) -> GeometrySpec:
    primitives = [PrimitiveSpec(**p) for p in data.get("primitives", [])]
    operations = [BooleanOpSpec(**o) for o in data.get("operations", [])]
    return GeometrySpec(
        primitives=primitives,
        operations=operations,
        description=data.get("description", original_text),
    )


def _word_to_int(s: str) -> int:
    """Convert a word-number or digit string to int."""
    try:
        return int(s)
    except ValueError:
        return _WORD_TO_NUM.get(s.lower(), 1)


class NLPAgent:
    """Parse natural language descriptions into GeometrySpec objects."""

    def __init__(self, openai_api_key: Optional[str] = None):
        # Legacy: keep openai_api_key for backward compat (used when no per-request config)
        self._default_openai_key = openai_api_key
        # Simple in-memory cache: cache_key -> GeometrySpec
        self._cache: Dict[str, GeometrySpec] = {}
        if openai_api_key:
            try:
                import openai  # noqa: F401
                logger.info("OpenAI integration enabled (default provider)")
            except ImportError:
                logger.warning("openai package not installed; falling back to rule-based NLP")

    async def parse_text(
        self,
        text: str,
        provider_config: Optional[AIProviderConfig] = None,
    ) -> GeometrySpec:
        """Main entry point: parse text -> GeometrySpec.

        When *provider_config* is given and its provider is not RULES, the
        request is forwarded to the appropriate AI backend.  Identical
        (text, provider, model) combinations are served from an in-memory cache
        so repeated UI submissions skip the LLM round-trip entirely.
        """
        # Build a deterministic cache key that includes provider settings
        config = provider_config or AIProviderConfig()
        cache_key = (
            f"{text.strip()}|{config.provider}|{config.model or ''}|{config.base_url or ''}"
        )

        if cache_key in self._cache:
            logger.debug("NLPAgent: cache hit for %r", cache_key[:80])
            return self._cache[cache_key]

        text_stripped = text.strip()
        text_lower = text_stripped.lower()

        result: Optional[GeometrySpec] = None

        # ---- Determine which backend to use --------------------------------
        provider = config.provider

        # If the caller didn't specify a provider but the legacy openai key is
        # present, fall back to the old behaviour.
        if provider == AIProvider.RULES and self._default_openai_key:
            provider = AIProvider.OPENAI
            config = AIProviderConfig(
                provider=AIProvider.OPENAI,
                api_key=self._default_openai_key,
            )

        try:
            if provider == AIProvider.OPENAI:
                result = await self._parse_with_openai(text_stripped, config)
            elif provider == AIProvider.ANTHROPIC:
                result = await self._parse_with_anthropic(text_stripped, config)
            elif provider == AIProvider.GOOGLE:
                result = await self._parse_with_google(text_stripped, config)
            elif provider in (AIProvider.OLLAMA, AIProvider.CUSTOM):
                result = await self._parse_with_openai_compatible(text_stripped, config)
        except Exception as exc:
            logger.warning(
                "NLPAgent: %s parse failed, falling back to rules: %s", provider, exc
            )

        if result is None:
            result = self._parse_with_rules(text_lower, original=text_stripped)

        self._cache[cache_key] = result
        return result

    # ------------------------------------------------------------------ #
    # Rule-based parser                                                    #
    # ------------------------------------------------------------------ #

    def _parse_with_rules(self, text: str, original: str = "") -> GeometrySpec:
        primitives: List[PrimitiveSpec] = []
        operations: List[BooleanOpSpec] = []
        warnings: List[str] = []
        confidence: float = 1.0

        # Check for boolean operations first
        has_subtract = any(kw in text for kw in ["subtract", "cut", "remove", "drill", "hole", "minus"])
        has_union = any(kw in text for kw in ["union", "combine", "merge", "add", "attach"])
        has_intersect = any(kw in text for kw in ["intersect", "intersection", "overlap", "common"])

        # ---------------------------------------------------------------- #
        # Pattern: N holes at corners (mounting bracket / panel patterns)  #
        # ---------------------------------------------------------------- #
        corner_holes = self._try_extract_corner_holes(text)
        if corner_holes:
            base_prims, hole_prims, hole_ops = corner_holes
            primitives.extend(base_prims)
            primitives.extend(hole_prims)
            operations.extend(hole_ops)
            return GeometrySpec(
                primitives=primitives,
                operations=operations,
                description=original or text,
                parse_confidence=0.85,
                warnings=warnings,
            )

        # ---------------------------------------------------------------- #
        # Sentence splitting strategy                                       #
        # Base splitters: always active (explicit delimiters + "from")      #
        # Boolean splitters: only when boolean keywords are present         #
        # Spatial splitters: always active (each is a separate primitive)   #
        # ---------------------------------------------------------------- #
        # Always split on these:
        base_split = r"\bthen\b|,|;|\bfrom\b|\bout\s+of\b|\bon\s+top\s+of\b|\babove\b|\bbelow\b|\bunder\b"
        sentences = re.split(base_split, text)

        if has_subtract:
            # Also split on "and" and "in a/an/the" for subtraction patterns
            # (e.g. "drill a hole in a box" → ["drill a hole", "box"])
            sentences = [
                s for seg in sentences
                for s in re.split(r"\band\b|\bin\s+(?:a|an|the)\b|\binside\s+(?:a|an|the)\b", seg)
            ]
        elif has_union or has_intersect:
            # Split on "and" and "with" for union/intersection patterns
            # (e.g. "merge a sphere with a box" → ["merge a sphere", "a box"])
            sentences = [
                s for seg in sentences
                for s in re.split(r"\band\b|\bwith\b", seg)
            ]
        # NOTE: when no boolean keywords, intentionally do NOT split on "and"
        # so that "torus with major radius Xmm and minor radius Ymm" stays whole.

        for sentence in sentences:
            sentence = sentence.strip()
            prim = self._extract_primitive(sentence)
            if prim is not None:
                primitives.append(prim)

        # If no primitives found, try the full text
        if not primitives:
            prim = self._extract_primitive(text)
            if prim:
                primitives.append(prim)

        # ---------------------------------------------------------------- #
        # Apply spatial transforms to second+ primitives                   #
        # ---------------------------------------------------------------- #
        if len(primitives) >= 2:
            self._apply_spatial_hints(text, primitives)

        # ---------------------------------------------------------------- #
        # Build boolean operations                                         #
        # ---------------------------------------------------------------- #
        if has_subtract and len(primitives) >= 2:
            # Build a chain of subtractions: ((prim0 - prim1) - prim2) ...
            op_idx = len(primitives)  # next available result index
            if len(primitives) == 2:
                operations.append(
                    BooleanOpSpec(
                        operation=BooleanOpType.SUBTRACTION,
                        operand_a=0,
                        operand_b=1,
                        name="subtraction",
                    )
                )
            else:
                # Chain: result0 = prim0 - prim1, result1 = result0 - prim2, ...
                operations.append(
                    BooleanOpSpec(
                        operation=BooleanOpType.SUBTRACTION,
                        operand_a=0,
                        operand_b=1,
                        name="subtraction_0",
                    )
                )
                for i in range(2, len(primitives)):
                    operations.append(
                        BooleanOpSpec(
                            operation=BooleanOpType.SUBTRACTION,
                            operand_a=op_idx,
                            operand_b=i,
                            name=f"subtraction_{i - 1}",
                        )
                    )
                    op_idx += 1
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

        # ---------------------------------------------------------------- #
        # Fallback / confidence                                            #
        # ---------------------------------------------------------------- #
        if not primitives:
            logger.warning("Could not parse primitives; using default 20mm cube")
            warnings.append(
                "No recognizable shape found in the description; "
                "defaulting to a 20mm cube. Try using keywords like "
                "'box', 'cylinder', 'sphere', 'cone', or 'torus'."
            )
            primitives.append(
                PrimitiveSpec(
                    type=PrimitiveType.BOX,
                    dimensions={"width": 20.0, "height": 20.0, "depth": 20.0},
                )
            )
            confidence = 0.1
        else:
            confidence = self._compute_confidence(text, primitives, operations)

        if confidence < 0.5:
            warnings.append(
                "Low-confidence parse: the description may be ambiguous. "
                "Consider rephrasing with explicit dimensions and shape names."
            )

        return GeometrySpec(
            primitives=primitives,
            operations=operations,
            description=original or text,
            parse_confidence=round(confidence, 3),
            warnings=warnings,
        )

    # ------------------------------------------------------------------ #
    # Corner-hole pattern extraction                                       #
    # ------------------------------------------------------------------ #

    def _try_extract_corner_holes(
        self, text: str
    ) -> Optional[Tuple[List[PrimitiveSpec], List[PrimitiveSpec], List[BooleanOpSpec]]]:
        """Detect patterns like '4 x 5mm holes in the corners' and build
        a base-primitive + N positioned cylinders + N subtraction operations."""
        m = _CORNER_HOLES_RE.search(text)
        m_nodim = _CORNER_HOLES_NO_DIM_RE.search(text) if m is None else None
        m_fallback = _N_HOLES_RE.search(text) if m is None and m_nodim is None else None

        if m is None and m_nodim is None and m_fallback is None:
            return None

        if m is not None:
            n_holes = _word_to_int(m.group(1))
            hole_raw = float(m.group(2))
            # Extract unit from the match context, not the full text, to avoid
            # false "in" matches from positional phrases like "holes in the corners"
            unit_m = re.search(r"\d+(?:\.\d+)?\s*(mm|cm|m|in|inch|inches)", m.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else "mm"
            hole_radius = self._to_mm(hole_raw, unit) / 2.0
        elif m_nodim is not None:
            n_holes = _word_to_int(m_nodim.group(1))
            # Default hole radius when not specified
            hole_radius = 3.0
        else:
            n_holes = _word_to_int(m_fallback.group(1))
            hole_raw = float(m_fallback.group(2))
            unit_m = re.search(r"\d+(?:\.\d+)?\s*(mm|cm|m|in|inch|inches)", m_fallback.group(0), re.IGNORECASE)
            unit = unit_m.group(1) if unit_m else "mm"
            hole_radius = self._to_mm(hole_raw, unit) / 2.0

        # Try to find a base shape
        base_sentences = re.split(r"\bwith\b", text, maxsplit=1)
        base_text = base_sentences[0].strip()
        base_prim = self._extract_primitive(base_text) if base_text else None

        if base_prim is None:
            # Try full text without hole clause
            stripped = re.sub(
                _CORNER_HOLES_RE.pattern + "|" + _CORNER_HOLES_NO_DIM_RE.pattern,
                "",
                text,
                flags=re.IGNORECASE,
            )
            base_prim = self._extract_primitive(stripped.strip())
        if base_prim is None:
            # Default bracket plate
            base_prim = PrimitiveSpec(
                type=PrimitiveType.BOX,
                dimensions={"width": 50.0, "height": 30.0, "depth": 10.0},
                name="base",
            )

        base_prims = [base_prim]
        d = base_prim.dimensions
        w = d.get("width", 50.0) / 2.0
        dep = d.get("depth", 30.0) / 2.0
        h = d.get("height", d.get("depth", 10.0))

        # Generate hole cylinder height slightly taller than base for clean boolean
        cyl_h = h + 2.0

        # Corner positions depend on how many holes are requested
        if n_holes == 4:
            offsets = [(-w * 0.7, -dep * 0.7), (w * 0.7, -dep * 0.7),
                       (-w * 0.7, dep * 0.7), (w * 0.7, dep * 0.7)]
        elif n_holes == 2:
            offsets = [(-w * 0.7, 0.0), (w * 0.7, 0.0)]
        elif n_holes == 3:
            offsets = [(-w * 0.7, -dep * 0.7), (w * 0.7, -dep * 0.7), (0.0, dep * 0.7)]
        elif n_holes == 6:
            offsets = [(-w * 0.7, -dep * 0.7), (0.0, -dep * 0.7), (w * 0.7, -dep * 0.7),
                       (-w * 0.7, dep * 0.7), (0.0, dep * 0.7), (w * 0.7, dep * 0.7)]
        else:
            # Generic: evenly space holes across width
            offsets = [((-w * 0.7) + i * (w * 1.4 / max(n_holes - 1, 1)), 0.0)
                       for i in range(n_holes)]

        hole_prims: List[PrimitiveSpec] = []
        for i, (ox, oy) in enumerate(offsets):
            t = Transform(
                position=Vector3(x=ox, y=oy, z=0.0),
            )
            hole_prims.append(
                PrimitiveSpec(
                    type=PrimitiveType.CYLINDER,
                    dimensions={"radius": hole_radius, "height": cyl_h},
                    transform=t,
                    name=f"hole_{i + 1}",
                )
            )

        # Build subtraction chain: result = base - hole1 - hole2 ...
        hole_ops: List[BooleanOpSpec] = []
        # Index 0 = base, indices 1..n = holes
        prev_result = 0
        op_result_idx = 1 + len(hole_prims)  # after all primitives
        for i in range(len(hole_prims)):
            hole_ops.append(
                BooleanOpSpec(
                    operation=BooleanOpType.SUBTRACTION,
                    operand_a=prev_result,
                    operand_b=i + 1,
                    name=f"drill_hole_{i + 1}",
                )
            )
            prev_result = op_result_idx
            op_result_idx += 1

        return base_prims, hole_prims, hole_ops

    # ------------------------------------------------------------------ #
    # Spatial transform inference                                          #
    # ------------------------------------------------------------------ #

    def _apply_spatial_hints(self, text: str, primitives: List[PrimitiveSpec]) -> None:
        """Mutate transforms of primitives based on spatial keywords.

        In phrases like "A on top of B", A is primitives[0] and B is primitives[1].
        A gets a positive Z offset so it sits on top of B.
        """
        if len(primitives) < 2:
            return

        if _SPATIAL_ON_TOP.search(text):
            # "A on top of B": primitives[0] (A) is placed on top of primitives[1] (B)
            base = primitives[1]
            placed = primitives[0]
            base_h = base.dimensions.get("height", base.dimensions.get("depth", 10.0))
            placed_h = placed.dimensions.get(
                "height", placed.dimensions.get("radius", 5.0) * 2
            )
            placed.transform.position.z = base_h / 2.0 + placed_h / 2.0
            return

        if _SPATIAL_BELOW.search(text):
            base = primitives[1]
            placed = primitives[0]
            base_h = base.dimensions.get("height", base.dimensions.get("depth", 10.0))
            placed_h = placed.dimensions.get(
                "height", placed.dimensions.get("radius", 5.0) * 2
            )
            placed.transform.position.z = -(base_h / 2.0 + placed_h / 2.0)
            return

        # For other hints, apply to all non-first primitives
        for prim in primitives[1:]:
            if _SPATIAL_CENTERED.search(text):
                prim.transform.position.x = 0.0
                prim.transform.position.y = 0.0

            offset_m = _SPATIAL_OFFSET.search(text)
            if offset_m:
                unit = offset_m.group(2) or "mm"
                offset_val = self._to_mm(float(offset_m.group(1)), unit)
                prim.transform.position.x = offset_val

            rot_m = _ROTATION_RE.search(text)
            if rot_m:
                angle = float(rot_m.group(1))
                axis = (rot_m.group(2) or "z").lower()
                if axis == "x":
                    prim.transform.rotation.x = angle
                elif axis == "y":
                    prim.transform.rotation.y = angle
                else:
                    prim.transform.rotation.z = angle

    # ------------------------------------------------------------------ #
    # Confidence scoring                                                   #
    # ------------------------------------------------------------------ #

    def _compute_confidence(
        self,
        text: str,
        primitives: List[PrimitiveSpec],
        operations: List[BooleanOpSpec],
    ) -> float:
        """Heuristic confidence: higher when explicit shape names and dimensions found."""
        score = 0.5

        # Reward each primitive that has a specific shape keyword in the text
        shape_keywords = {
            "box": ["box", "cube", "block", "rectangular", "prism"],
            "cylinder": ["cylinder", "tube", "pipe", "rod", "shaft", "disc", "disk"],
            "sphere": ["sphere", "ball", "globe", "orb"],
            "cone": ["cone", "pyramid", "taper"],
            "torus": ["torus", "ring", "donut", "doughnut"],
        }
        for prim in primitives:
            ptype = str(prim.type).lower()
            kws = shape_keywords.get(ptype, [])
            if any(kw in text for kw in kws):
                score += 0.15

        # Reward explicit dimensions
        if re.search(r"\d+\s*(?:mm|cm|m|in|inch)", text, re.IGNORECASE):
            score += 0.15

        # Reward explicit boolean keywords
        bool_kws = ["subtract", "union", "intersect", "combine", "cut", "merge", "drill"]
        if any(kw in text for kw in bool_kws) and operations:
            score += 0.1

        # Penalise very short or keyword-sparse text
        if len(text.split()) < 3:
            score -= 0.2

        return max(0.05, min(1.0, score))

    # ------------------------------------------------------------------ #
    # Primitive extractors                                                 #
    # ------------------------------------------------------------------ #

    def _extract_primitive(self, text: str) -> Optional[PrimitiveSpec]:
        """Try to extract a single primitive from text."""
        if any(kw in text for kw in ["box", "cube", "block", "rectangular", "prism", "rect", "bracket", "plate", "panel"]):
            return self._parse_box(text)
        # capsule / disc / disk / puck / hole / bore are cylinder-like shapes
        if any(kw in text for kw in ["cylinder", "tube", "pipe", "rod", "shaft", "capsule", "disc", "disk", "puck", "hole", "bore", "opening"]):
            return self._parse_cylinder(text)
        if any(kw in text for kw in ["sphere", "ball", "globe", "orb"]):
            return self._parse_sphere(text)
        if any(kw in text for kw in ["cone", "pyramid", "taper"]):
            return self._parse_cone(text)
        if any(kw in text for kw in ["torus", "ring", "donut", "doughnut", "annulus"]):
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
        r_match = re.search(r"\bradius\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if r_match:
            radius = self._to_mm(float(r_match.group(1)), self._find_unit(text))
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
        r_match = re.search(r"\bradius\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        if r_match:
            radius = self._to_mm(float(r_match.group(1)), self._find_unit(text))
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
        # Support named major/minor radius extraction
        major_m = re.search(r"major\s+radius\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        minor_m = re.search(r"minor\s+radius\s+(\d+(?:\.\d+)?)", text, re.IGNORECASE)
        unit = self._find_unit(text)
        if major_m and minor_m:
            major_r = self._to_mm(float(major_m.group(1)), unit)
            minor_r = self._to_mm(float(minor_m.group(1)), unit)
        else:
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
        # Try NxNxN  (ASCII x/X, *, × Unicode)
        m = re.search(
            r"(\d+(?:\.\d+)?)\s*[xX\*×]\s*(\d+(?:\.\d+)?)\s*[xX\*×]\s*(\d+(?:\.\d+)?)",
            text,
        )
        if m:
            return [self._to_mm(float(m.group(i)), unit) for i in (1, 2, 3)]
        # Try NxN
        m = re.search(r"(\d+(?:\.\d+)?)\s*[xX\*×]\s*(\d+(?:\.\d+)?)", text)
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
        """Detect unit of measurement.

        Uses word boundaries for wordy units like 'in'/'inch'/'inches' so that
        words like 'cylinder', 'aluminum', 'machine', 'inside', etc. don't
        accidentally trigger the inch conversion.  Metric abbreviations are
        safe to check without boundaries since 'mm'/'cm' rarely appear inside
        English words.
        """
        # Priority: longer/more-specific first
        if re.search(r"\binches\b", text, re.IGNORECASE):
            return "inches"
        if re.search(r"\binch\b", text, re.IGNORECASE):
            return "inch"
        if re.search(r"\bin\b", text, re.IGNORECASE):
            return "in"
        # Metric abbreviations — simple substring is safe
        if "mm" in text.lower():
            return "mm"
        if "cm" in text.lower():
            return "cm"
        # Standalone meter — must be preceded by a digit (to avoid lone "m" in words)
        if re.search(r"\d\s*m\b(?!m)", text, re.IGNORECASE):
            return "m"
        return "mm"

    @staticmethod
    def _to_mm(value: float, unit: str) -> float:
        factor = UNIT_FACTORS.get(unit.lower(), 1.0)
        return round(value * factor, 4)

    # ------------------------------------------------------------------ #
    # AI provider backends                                                 #
    # ------------------------------------------------------------------ #

    async def _parse_with_openai(
        self, text: str, config: AIProviderConfig
    ) -> GeometrySpec:
        """Use an OpenAI GPT model to parse the description."""
        import openai

        api_key = config.api_key or self._default_openai_key
        if not api_key:
            raise ValueError("OpenAI API key is required")
        model = config.model or PROVIDER_DEFAULT_MODELS[AIProvider.OPENAI]
        client = openai.AsyncOpenAI(api_key=api_key)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        raw = _strip_json_fences(response.choices[0].message.content)
        logger.info("NLPAgent: OpenAI (%s) parse complete", model)
        return _build_geometry_spec_from_dict(json.loads(raw), text)

    async def _parse_with_anthropic(
        self, text: str, config: AIProviderConfig
    ) -> GeometrySpec:
        """Use an Anthropic Claude model to parse the description."""
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. "
                "Run: pip install anthropic"
            ) from exc

        api_key = config.api_key
        if not api_key:
            raise ValueError("Anthropic API key is required")
        model = config.model or PROVIDER_DEFAULT_MODELS[AIProvider.ANTHROPIC]
        client = anthropic.AsyncAnthropic(api_key=api_key)
        message = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": text}],
        )
        raw = _strip_json_fences(message.content[0].text)
        logger.info("NLPAgent: Anthropic (%s) parse complete", model)
        return _build_geometry_spec_from_dict(json.loads(raw), text)

    async def _parse_with_google(
        self, text: str, config: AIProviderConfig
    ) -> GeometrySpec:
        """Use a Google Gemini model to parse the description."""
        try:
            import google.generativeai as genai
        except ImportError as exc:
            raise ImportError(
                "google-generativeai package is not installed. "
                "Run: pip install google-generativeai"
            ) from exc

        api_key = config.api_key
        if not api_key:
            raise ValueError("Google API key is required")
        model_name = config.model or PROVIDER_DEFAULT_MODELS[AIProvider.GOOGLE]
        genai.configure(api_key=api_key)
        gmodel = genai.GenerativeModel(
            model_name, system_instruction=_SYSTEM_PROMPT
        )
        response = await gmodel.generate_content_async(text)
        raw = _strip_json_fences(response.text)
        logger.info("NLPAgent: Google Gemini (%s) parse complete", model_name)
        return _build_geometry_spec_from_dict(json.loads(raw), text)

    async def _parse_with_openai_compatible(
        self, text: str, config: AIProviderConfig
    ) -> GeometrySpec:
        """Use any OpenAI-compatible API (Ollama, LM Studio, vLLM, …)."""
        try:
            import openai
        except ImportError as exc:
            raise ImportError(
                "openai package is not installed. Run: pip install openai"
            ) from exc

        if config.provider == AIProvider.OLLAMA:
            base_url = config.base_url or "http://localhost:11434/v1"
            api_key = config.api_key or "ollama"
        else:
            # CUSTOM provider
            base_url = config.base_url
            if not base_url:
                raise ValueError(
                    "base_url is required for the custom provider"
                )
            api_key = config.api_key or "none"

        model = config.model or PROVIDER_DEFAULT_MODELS.get(config.provider, "llama3")
        client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        raw = _strip_json_fences(response.choices[0].message.content)
        logger.info(
            "NLPAgent: OpenAI-compatible (%s @ %s) parse complete", model, base_url
        )
        return _build_geometry_spec_from_dict(json.loads(raw), text)
