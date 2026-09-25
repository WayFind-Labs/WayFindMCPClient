"""
services/media_service.py
Internal media processing client (stub).

NOTE (v2 architecture):
Primary image intake, MIME validation, and safety scanning live in ShelterAppUiBackend.
This service provides an internal stub interface in case backend-level media verification
is needed.
"""

from __future__ import annotations

import logging
import uuid
from functools import lru_cache

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class MediaService:
    """Async client for internal media processing and safety scanning."""

    def __init__(self, base_url: str = "", timeout: float = 10.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def safety_scan(self, file_bytes: bytes, mime_type: str) -> dict:
        """Scan media file bytes for safety compliance."""
        if self.base_url:
            try:
                client = self._get_client()
                response = await client.post(
                    "/api/media/scan",
                    content=file_bytes,
                    headers={"Content-Type": mime_type},
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as exc:
                logger.warning("MediaService safety_scan failed over HTTP: %s", exc)

        return {"safe": True, "flags": [], "file_size": len(file_bytes)}

    async def store(self, file_bytes: bytes, mime_type: str) -> str:
        """Store media and return an opaque media ID."""
        media_id = f"media-{uuid.uuid4().hex[:12]}"
        if self.base_url:
            try:
                client = self._get_client()
                response = await client.post(
                    "/api/media/store",
                    content=file_bytes,
                    headers={"Content-Type": mime_type},
                )
                if response.status_code in (200, 201):
                    return response.json().get("media_id", media_id)
            except Exception as exc:
                logger.warning("MediaService store failed over HTTP: %s", exc)

        return media_id


@lru_cache(maxsize=1)
def get_media_service() -> MediaService:
    """Return singleton MediaService configured from settings."""
    settings = get_settings()
    url = getattr(settings, "media_safety_scan_url", "")
    return MediaService(base_url=url)
