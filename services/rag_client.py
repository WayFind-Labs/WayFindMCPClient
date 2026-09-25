"""
services/rag_client.py
HTTP client for the RAG knowledge-base service (Qdrant / vector search).

Endpoints called:
  POST /api/guidance/query -> GuidanceResult
"""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.config import get_settings
from schemas.guidance import GuidanceResult

logger = logging.getLogger(__name__)

_DEFAULT_GUIDANCE = (
    "• If you have found an unaccompanied child, please remain with them in a safe, "
    "public area and notify local police immediately.\n"
    "• If your child is missing, file a first information report (FIR) with police "
    "and provide recent photographs and distinctive clothing details.\n"
    "• For shelter intake, use our search service to find authorized facilities near you."
)


_TOPIC_GUIDANCE: dict[str, str] = {
    "found_child": (
        "• Stay with the child in a safe, public location.\n"
        "• Contact local police or child protection authorities immediately.\n"
        "• Do not share the child's photo or identity on personal social media accounts.\n"
        "• Comfort the child and wait for official child welfare personnel to arrive."
    ),
    "missing_child": (
        "• File an immediate report with the nearest police station.\n"
        "• Provide the latest clear photos and distinctive physical details.\n"
        "• Submit the report to Wayfind to check against our authorized intake records."
    ),
    "shelter": (
        "• Use authorized child-intake shelters and government bureaus only.\n"
        "• Always request official documentation and an intake receipt."
    ),
    "safety": (
        "• Never leave an unaccompanied child alone.\n"
        "• Always remain in well-lit, public spaces when waiting for authorities."
    ),
}


class RagClient:
    """Async HTTP client for the RAG knowledge-base backend."""

    def __init__(self, base_url: str = "", timeout: float = 8.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def query(
        self,
        query: str,
        topic: str | None = None,
    ) -> GuidanceResult:
        """Query knowledge base for contextual guidance."""
        resolved_topic = (topic or "").strip().lower() or None

        if self.base_url:
            try:
                client = self._get_client()
                response = await client.post(
                    "/api/guidance/query",
                    json={"query": query, "topic": resolved_topic},
                )
                if response.status_code == 200:
                    data = response.json()
                    return GuidanceResult.model_validate(data)
            except Exception as exc:
                logger.warning("RagClient query failed over HTTP: %s", exc)

        # Fallback guidance
        guidance_text = _TOPIC_GUIDANCE.get(resolved_topic or "", _DEFAULT_GUIDANCE)
        return GuidanceResult(
            guidance=guidance_text,
            next_steps=[
                "Follow official safety procedures",
                "Contact official emergency services",
                "Keep documentation and case reference numbers ready",
            ],
            topic=resolved_topic or "general",
            is_static_fallback=True,
        )


@lru_cache(maxsize=1)
def get_rag_client() -> RagClient:
    """Return singleton RagClient configured from settings."""
    settings = get_settings()
    url = getattr(settings, "rag_service_url", "")
    return RagClient(base_url=url)
