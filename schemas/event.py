"""
schemas/event.py
Input and output event types for the internal agent API (v2).

These models define the contract between ShelterAppUiBackend and WayFindMCPClient.
The frontend never sees these types directly.

IncomingEvent  — sent by ShelterAppUiBackend to this service
AgentEvent     — returned by this service to ShelterAppUiBackend
InternalRequest — top-level request body wrapping IncomingEvent

Event types:
  Incoming:
    user_message       — user typed text
    user_image         — user uploaded an image (media_id already set)
    user_form_response — user filled in structured follow-up fields

  Outgoing:
    assistant_message   — conversational reply from the agent
    request_information — agent needs more info; fields list names required
    request_image       — agent asks user to upload a photo
    search_started      — signal that a search is running (show spinner)
    search_results      — candidate results (no PII)
    review_pending      — potential match found; under human review
    submission_complete — report submitted successfully
    error               — something failed; safe user-facing message
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator


class IncomingEvent(BaseModel):
    """A single event sent by ShelterAppUiBackend on behalf of the user."""

    type: str = Field(
        description="Event type: user_message | user_image | user_form_response",
    )
    content: str | None = Field(
        default=None,
        max_length=4000,
        description="User's text content. Required for user_message.",
    )
    media_id: str | None = Field(
        default=None,
        description=(
            "Opaque media ID issued by ShelterAppUiBackend after safety scan and storage. "
            "Never a raw file path or object-storage URL."
        ),
    )
    form_data: dict[str, Any] | None = Field(
        default=None,
        description="Structured follow-up form answers keyed by field name.",
    )

    @field_validator("media_id")
    @classmethod
    def validate_opaque_media_id(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if "://" in v or "/" in v or "\\" in v:
            raise ValueError("media_id must be an opaque identifier, not a URL or file path")
        return v


class InternalRequest(BaseModel):
    """Body of POST /internal/sessions/{session_id}/events."""

    event: IncomingEvent


class AgentEvent(BaseModel):
    """A single output event returned to ShelterAppUiBackend."""

    type: str = Field(
        description=(
            "assistant_message | request_information | request_image | "
            "search_started | search_results | review_pending | "
            "submission_complete | error"
        )
    )
    # Present on: assistant_message, error (use 'message' for error)
    content: str | None = None

    # request_information: list of field names the agent needs
    fields: list[str] | None = None

    # request_image / error: human-readable message
    message: str | None = None

    # search_results: list of result dicts (no PII — case IDs + coarse metadata)
    results: list[dict[str, Any]] | None = None

    # submission_complete: the new record / case reference
    record_id: str | None = None

    # review_pending: reference for the human-review submission
    case_reference: str | None = None
