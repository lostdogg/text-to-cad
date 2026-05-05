"""AI provider configuration model."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AIProvider(str, Enum):
    RULES = "rules"        # Built-in rule-based parser (no API key needed)
    OPENAI = "openai"      # OpenAI GPT models
    ANTHROPIC = "anthropic"  # Anthropic Claude models
    GOOGLE = "google"      # Google Gemini models
    OLLAMA = "ollama"      # Ollama local models (OpenAI-compatible)
    CUSTOM = "custom"      # Any OpenAI-compatible API with a custom base URL


# Default models per provider
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    AIProvider.OPENAI: "gpt-4o",
    AIProvider.ANTHROPIC: "claude-3-5-sonnet-20241022",
    AIProvider.GOOGLE: "gemini-1.5-flash",
    AIProvider.OLLAMA: "llama3",
    AIProvider.CUSTOM: "gpt-4o",
}

# Human-readable provider info exposed to the frontend
PROVIDER_INFO: list[dict] = [
    {
        "provider": AIProvider.RULES,
        "label": "Rule-Based (No API key)",
        "description": "Built-in pattern matcher. Fast and offline; less flexible.",
        "requires_key": False,
        "requires_base_url": False,
        "default_model": None,
    },
    {
        "provider": AIProvider.OPENAI,
        "label": "OpenAI (GPT-4o, GPT-4, …)",
        "description": "Use OpenAI GPT models via the OpenAI API.",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": PROVIDER_DEFAULT_MODELS[AIProvider.OPENAI],
    },
    {
        "provider": AIProvider.ANTHROPIC,
        "label": "Anthropic (Claude)",
        "description": "Use Anthropic Claude models via the Anthropic API.",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": PROVIDER_DEFAULT_MODELS[AIProvider.ANTHROPIC],
    },
    {
        "provider": AIProvider.GOOGLE,
        "label": "Google (Gemini)",
        "description": "Use Google Gemini models via the Google AI API.",
        "requires_key": True,
        "requires_base_url": False,
        "default_model": PROVIDER_DEFAULT_MODELS[AIProvider.GOOGLE],
    },
    {
        "provider": AIProvider.OLLAMA,
        "label": "Ollama (local)",
        "description": "Run models locally with Ollama. No API key needed.",
        "requires_key": False,
        "requires_base_url": False,
        "default_model": PROVIDER_DEFAULT_MODELS[AIProvider.OLLAMA],
    },
    {
        "provider": AIProvider.CUSTOM,
        "label": "Custom (OpenAI-compatible)",
        "description": "Any OpenAI-compatible API endpoint (e.g. LM Studio, vLLM, Together AI).",
        "requires_key": False,
        "requires_base_url": True,
        "default_model": None,
    },
]


class AIProviderConfig(BaseModel):
    """Per-request AI provider configuration."""

    provider: AIProvider = Field(
        AIProvider.RULES,
        description="Which AI provider to use for NLP parsing",
    )
    api_key: Optional[str] = Field(
        None,
        description="API key for the chosen provider (not stored server-side)",
    )
    model: Optional[str] = Field(
        None,
        description="Model name override; uses the provider default when omitted",
    )
    base_url: Optional[str] = Field(
        None,
        description="Base URL override (required for Ollama and Custom providers)",
    )
