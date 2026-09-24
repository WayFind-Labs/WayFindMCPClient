"""
schemas/location.py
Geographic location model used across search tools and service clients.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Location(BaseModel):
    """A geographic point or named place.

    Either ``label`` (free-text) or lat/lon may be provided.
    ``radius_km`` defines a search radius around the point.
    All fields are optional — the search service decides how to handle partial data.
    """

    label: str | None = Field(
        default=None,
        description="Human-readable place name or address (e.g. 'Johar Town, Lahore').",
    )
    latitude: float | None = Field(
        default=None,
        ge=-90.0,
        le=90.0,
        description="WGS-84 latitude in decimal degrees.",
    )
    longitude: float | None = Field(
        default=None,
        ge=-180.0,
        le=180.0,
        description="WGS-84 longitude in decimal degrees.",
    )
    radius_km: float | None = Field(
        default=None,
        gt=0.0,
        description="Search radius in kilometres around the lat/lon point.",
    )
