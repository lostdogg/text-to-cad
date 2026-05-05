"""Application configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from typing import List, Optional

try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings  # type: ignore[no-redef,assignment]

from pydantic import Field


class Settings(BaseSettings):
    """All configurable application settings."""

    # Runtime mode
    MODE: str = Field("local", description="'cloud' or 'local'")

    # Optional OpenAI key for GPT-4 NLP fallback
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API key")

    # Optional keys for other AI providers (used as server-side defaults only;
    # per-request keys supplied by the client always take precedence)
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API key")
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Google AI / Gemini API key")
    OLLAMA_BASE_URL: str = Field(
        "http://localhost:11434/v1",
        description="Base URL for a local Ollama instance",
    )

    # Server
    HOST: str = Field("0.0.0.0", description="Bind host")
    PORT: int = Field(8000, description="Bind port")

    # CORS
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "*"],
        description="Allowed CORS origins",
    )

    # Worker threads for CPU-bound tasks
    MAX_WORKERS: int = Field(4, description="Thread pool workers")

    # Export directory (relative or absolute)
    EXPORT_DIR: str = Field("exports", description="Directory for exported files")

    # Model storage (in-memory by default; could be a DB URI)
    DATABASE_URL: Optional[str] = Field(None, description="Optional database URL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
