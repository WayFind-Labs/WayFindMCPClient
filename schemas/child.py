"""
schemas/child.py
Data models for missing-child search criteria and found-child reports.

Design rules (enforced via docstrings + comments, not validators):
  - LLM must NEVER invent values. Only fill fields the user explicitly stated.
  - Leave fields None where user said nothing or "I don't know".
  - Set [] for clothing/features only where user explicitly said "none".
  - age.exact only if the user said an exact number ("she is 9 years old").
  - age.min/max for approximations ("around 9", "between 8 and 10").
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgeRange(BaseModel):
    """Represents an age with optional exact value or min/max range.

    Use ``exact`` only when the user states a precise age.
    Use ``min`` / ``max`` for approximate ages ("around 9" → min=8, max=10).
    All three fields may be None if age is completely unknown.
    """

    min: int | None = Field(default=None, ge=0, le=120, description="Lower bound of age range (inclusive).")
    max: int | None = Field(default=None, ge=0, le=120, description="Upper bound of age range (inclusive).")
    exact: int | None = Field(default=None, ge=0, le=120, description="Exact age — set ONLY when user gave a precise number.")


class HeightRange(BaseModel):
    """Represents height in centimetres as an optional range."""

    min_cm: float | None = Field(default=None, ge=0.0, le=300.0, description="Minimum height in cm.")
    max_cm: float | None = Field(default=None, ge=0.0, le=300.0, description="Maximum height in cm.")


class ChildSearchCriteria(BaseModel):
    """Structured criteria for searching missing-child intake records.

    Built incrementally across conversation turns.  The LLM merges each new
    user message into the existing instance — it must not reset fields that the
    user has already provided.

    Minimum required for a search: gender, age (any form), last_seen_location.
    """

    age: AgeRange = Field(default_factory=AgeRange, description="Age range or exact age of the child.")
    gender: str | None = Field(
        default=None,
        description='Reported gender. Accepted values: "male" | "female" | "unknown".',
    )
    height: HeightRange = Field(default_factory=HeightRange, description="Height range in centimetres.")
    hair_color: str | None = Field(default=None, description="Hair colour as described by the user.")
    eye_color: str | None = Field(default=None, description="Eye colour as described by the user.")
    skin_tone: str | None = Field(default=None, description="Skin tone as described by the user.")
    clothing: list[str] = Field(
        default_factory=list,
        description="List of clothing items described. Empty list means no clothing info provided.",
    )
    identifying_features: list[str] = Field(
        default_factory=list,
        description="Scars, birthmarks, tattoos, or other distinguishing features.",
    )
    last_seen_location: str | None = Field(
        default=None,
        description="Free-text location where child was last seen. Required for search.",
    )
    date_missing: str | None = Field(
        default=None,
        description="ISO 8601 date (YYYY-MM-DD) when child was reported missing.",
    )
    time_missing: str | None = Field(
        default=None,
        description="ISO 8601 time (HH:MM) when child was last seen.",
    )
    description: str | None = Field(
        default=None,
        description="Free-text catch-all for details that don't fit other fields.",
    )


class FoundChildReport(BaseModel):
    """Report submitted when a user has found an unaccompanied child.

    ``found_location`` is the only required field — everything else is optional
    but encouraged for better matching.

    ``media_reference`` stores only an internal backend media ID — never a
    raw URL, file path, or base64 string.
    """

    approx_age: AgeRange = Field(default_factory=AgeRange, description="Approximate age of the found child.")
    gender: str | None = Field(
        default=None,
        description='Observed gender. Accepted values: "male" | "female" | "unknown".',
    )
    height: HeightRange = Field(default_factory=HeightRange, description="Estimated height in centimetres.")
    hair_color: str | None = Field(default=None, description="Hair colour of the found child.")
    clothing: list[str] = Field(default_factory=list, description="Clothing the child is wearing.")
    identifying_features: list[str] = Field(
        default_factory=list,
        description="Visible distinguishing features on the found child.",
    )
    found_location: str = Field(description="Location where the child was found. Required.")
    found_at: str | None = Field(
        default=None,
        description="ISO 8601 datetime when the child was found.",
    )
    current_circumstances: str | None = Field(
        default=None,
        description="Current situation — e.g. child is safe, distressed, injured.",
    )
    authorities_contacted: bool | None = Field(
        default=None,
        description="Whether local police or child-welfare authorities have been contacted.",
    )
    reporter_name: str | None = Field(default=None, description="Name of the person submitting the report.")
    reporter_contact: str | None = Field(
        default=None,
        description="Contact information for the reporter (phone / email).",
    )
    description: str | None = Field(
        default=None,
        description="Free-text narrative with any additional relevant details.",
    )
    media_reference: str | None = Field(
        default=None,
        description="Internal media ID from the media service. Never a raw URL or file path.",
    )


class ChildRegistrationData(BaseModel):
    """Data submitted when a guardian is pre-registering a safe child on Wayfind."""

    name: str | None = Field(default=None, description="Full name or nickname of the child.")
    gender: str | None = Field(
        default=None,
        description='Child gender. Accepted values: "male" | "female" | "other".',
    )
    age: AgeRange = Field(default_factory=AgeRange, description="Exact age or age range of the child.")
    city: str | None = Field(default=None, description="Home city or residential neighborhood.")
    identifying_features: list[str] = Field(
        default_factory=list,
        description="Distinguishing birthmarks, scars, or physical features.",
    )
    medical_notes: str | None = Field(
        default=None,
        description="Known medical conditions, allergies, or emergency medical info.",
    )
    emergency_contact: str | None = Field(
        default=None,
        description="Guardian phone number or primary emergency contact.",
    )

