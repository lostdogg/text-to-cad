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
        # capsule / disc / disk / puck are cylinder-like shapes
        if any(kw in text for kw in ["cylinder", "tube", "pipe", "rod", "shaft", "capsule", "disc", "disk", "puck"]):
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
