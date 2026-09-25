"""
app/config.py
Pydantic Settings — loads all configuration from environment variables / .env file.

Access anywhere via: from app.config import get_settings; settings = get_settings()
The @lru_cache ensures the Settings object is only constructed once per process.

NOTE (v2 architecture): This service is internal-only. CORS, rate-limiting, auth,
and image intake are handled by ShelterAppUiBackend. This service validates
requests via a shared API key (SHELTER_BACKEND_API_KEY).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the Wayfind agent backend.

    Values are loaded from environment variables (case-insensitive).
    Falls back to .env file in the project root if the variable is not set.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM Provider ──────────────────────────────────────────────────────────
    llm_provider: str = "gemini"
    gemini_api_key: str = ""
    openai_api_key: str = ""

    # ── Downstream Service URLs ───────────────────────────────────────────────
    postgres_service_url: str = ""
    rag_service_url: str = ""
    image_backend_url: str = ""
    support_service_url: str = ""
    review_service_url: str = ""

    # ── Media Safety Scan ─────────────────────────────────────────────────────
    media_safety_scan_url: str = ""

    # ── Session Backend ───────────────────────────────────────────────────────
    session_backend: str = "redis"   # "memory" | "redis"
    redis_url: str = "redis://localhost:6379/0"

    # ── Candidate Pool Limits ─────────────────────────────────────────────────
    max_candidate_pool: int = 50
    max_image_candidates: int = 20

    # ── Internal Auth (shared secret with ShelterAppUiBackend) ─────────────────
    # All public auth, CORS, and rate-limiting live in ShelterAppUiBackend.
    # This service only validates the X-Internal-Key header.
    shelter_backend_api_key: str = "changeme-dev-secret"

    # ── Internal Server ───────────────────────────────────────────────────────
    internal_host: str = "0.0.0.0"
    internal_port: int = 8000

    # ── MCP Transport ─────────────────────────────────────────────────────────
    mcp_transport: str = "sse"       # "sse" | "stdio"
    mcp_server_url: str = "http://localhost:9000/sse"

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        allowed = {"gemini", "openai"}
        if v.lower() not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}, got: {v!r}")
        return v.lower()

    @field_validator("session_backend")
    @classmethod
    def validate_session_backend(cls, v: str) -> str:
        allowed = {"memory", "redis"}
        if v.lower() not in allowed:
            raise ValueError(f"session_backend must be one of {allowed}, got: {v!r}")
        return v.lower()

    @field_validator("mcp_transport")
    @classmethod
    def validate_mcp_transport(cls, v: str) -> str:
        allowed = {"sse", "stdio"}
        if v.lower() not in allowed:
            raise ValueError(f"mcp_transport must be one of {allowed}, got: {v!r}")
        return v.lower()

    @field_validator("shelter_backend_api_key")
    @classmethod
    def validate_api_key_not_empty(cls, v: str) -> str:
        if not v or v == "changeme-dev-secret":
            import logging
            logging.getLogger(__name__).warning(
                "SHELTER_BACKEND_API_KEY is using the default dev value. "
                "Set a strong random value in production."
            )
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton.

    Use this everywhere instead of constructing Settings() directly so that
    environment variables are only read once.
    """
    return Settings()
