"""Opt-in synthetic rehearsal against the configured Groq model."""

import pytest

from app.config import get_settings
from agent.state import Intent, initial_state
from mcp_client.llm import WayfindLLM


@pytest.mark.asyncio
async def test_live_groq_found_child_intake():
    settings = get_settings()
    if settings.llm_provider != "groq" or not settings.groq_api_key:
        pytest.skip("Groq credentials are not configured")
    llm = WayfindLLM(
        provider="groq", api_key=settings.groq_api_key, model=settings.llm_model
    )
    intent = await llm.extract_intent(
        conversation_history=[],
        prompt="I found an unaccompanied child near a synthetic market. I need to record a report.",
    )
    assert intent.intent == Intent.FOUND_CHILD
    interruption = await llm.extract_intent(
        conversation_history=[
            {"role": "user", "content": "I found a child near a synthetic market."},
            {"role": "assistant", "content": "Please tell me where you found the child."},
        ],
        prompt="Before that, can I post the child's photo online?",
    )
    assert interruption.intent == Intent.GUIDANCE
    field_statuses: dict[str, str] = {}
    report = await llm.extract_found_child_report(
        existing_report=None,
        prompt="I found a child around 6 to 8 years old near a synthetic market. They wore a red shirt.",
        field_statuses=field_statuses,
    )
    assert report.found_location and "market" in report.found_location.lower()
    assert report.clothing and "red" in report.clothing[0].lower()
    assert report.approx_age.min == 6 and report.approx_age.max == 8
    assert field_statuses["found_location"] == "known"
    assert field_statuses["clothing"] == "known"
    assert field_statuses["approx_age"] == "known"
    state = initial_state("synthetic-groq-guidance")
    state["user_prompt"] = "Can I post the child's photo and location on social media?"
    guidance = await llm.generate_guidance_response(state)
    lower = guidance.lower()
    assert any(word in lower for word in ("photo", "image", "picture"))
    assert any(word in lower for word in ("avoid", "don't", "do not", "never", "no", "shouldn't")), guidance
