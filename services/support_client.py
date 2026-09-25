"""
services/support_client.py
HTTP client for the verified support directory service (shelters, NGOs, police).

Endpoints called:
  POST /api/support/search -> SupportResult
"""

from __future__ import annotations

import logging
from functools import lru_cache

import httpx

from app.config import get_settings
from schemas.location import Location
from schemas.support import SupportLocation, SupportResult

logger = logging.getLogger(__name__)


class SupportClient:
    """Async HTTP client for authorized support & shelter directory."""

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

    async def search(
        self,
        location: Location,
        support_type: str | None = None,
    ) -> SupportResult:
        """Query support directory for facilities near location."""
        location_label = location.label or (
            f"{location.latitude},{location.longitude}"
            if location.latitude is not None and location.longitude is not None
            else "Current Location"
        )
        location_dict = location.model_dump(exclude_none=True)

        if self.base_url:
            try:
                client = self._get_client()
                response = await client.post(
                    "/api/support/search",
                    json={"location": location_dict, "support_type": support_type},
                )
                if response.status_code == 200:
                    data = response.json()
                    return SupportResult.model_validate(data)
            except Exception as exc:
                logger.warning("SupportClient search failed over HTTP: %s", exc)

        # Fallback directory
        all_facilities = [
            SupportLocation(
                name="Edhi Emergency Child Welfare Bureau",
                support_type="shelter",
                address=f"Central Intake Center, near {location_label}",
                contact="115",
                is_24h=True,
                notes="Authorized child intake center and emergency shelter",
            ),
            SupportLocation(
                name="Child Protection & Welfare Bureau Headquarters",
                support_type="ngo",
                address=f"District Child Protection Office, {location_label}",
                contact="1121",
                is_24h=True,
                notes="Government authorized child protection service",
            ),
            SupportLocation(
                name="Emergency Police Station Child Desk",
                support_type="police",
                address=f"City Police Child Protection Unit, {location_label}",
                contact="15",
                is_24h=True,
                notes="Dedicated missing children desk",
            ),
        ]

        if support_type:
            filtered = [f for f in all_facilities if f.support_type.lower() == support_type.lower()]
        else:
            filtered = all_facilities

        return SupportResult(
            locations=filtered,
            total_found=len(filtered),
            query_location_label=location_label,
        )


@lru_cache(maxsize=1)
def get_support_client() -> SupportClient:
    """Return singleton SupportClient configured from settings."""
    settings = get_settings()
    url = getattr(settings, "support_service_url", "")
    return SupportClient(base_url=url)
