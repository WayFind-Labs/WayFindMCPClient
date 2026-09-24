"""
schemas/support.py
Return types from the search_support MCP tool.

A "shelter" in Wayfind context is an AUTHORIZED child-intake location only —
not a generic homeless shelter.  The support_type field controls filtering.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class SupportLocation(BaseModel):
    """A single support organisation or shelter returned by a search.

    ``contact`` is intentionally a free-text string to accommodate
    phone numbers, email addresses, or website URLs from various sources.
    """

    name: str = Field(description="Official name of the organisation or shelter.")
    support_type: str = Field(
        description='Category. Values: "shelter" | "ngo" | "police" | "hospital" | "other".',
    )
    address: str | None = Field(default=None, description="Street address or locality.")
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    distance_km: float | None = Field(
        default=None,
        ge=0.0,
        description="Distance in km from the search location (if geocoding was available).",
    )
    contact: str | None = Field(
        default=None,
        description="Phone number, email, or website for the organisation.",
    )
    operating_hours: str | None = Field(
        default=None,
        description="Operating hours as a free-text string (e.g. 'Mon–Fri 09:00–17:00').",
    )
    is_24h: bool | None = Field(
        default=None,
        description="True if the location operates 24 hours a day.",
    )
    notes: str | None = Field(
        default=None,
        description="Any additional public-facing notes about this location.",
    )


class SupportResult(BaseModel):
    """Aggregated results from a search_support call."""

    locations: list[SupportLocation] = Field(
        description="Matching locations, nearest first.",
    )
    total_found: int = Field(ge=0, description="Total matching locations before any limit was applied.")
    search_radius_km: float | None = Field(
        default=None,
        description="Effective search radius used (km).",
    )
    query_location_label: str | None = Field(
        default=None,
        description="Resolved location label used for the search.",
    )
    message: str | None = Field(
        default=None,
        description="Optional informational message (e.g. 'No results within 10 km; showing nearest 5').",
    )
