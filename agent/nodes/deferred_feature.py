"""Explain unavailable roadmap features without invoking their synthetic pipelines."""

from __future__ import annotations

from agent.state import Intent, WayfindState


_DEFERRED_MESSAGES = {
    Intent.MISSING_CHILD: (
        "I'm sorry your child is missing. Wayfind cannot search missing-child "
        "records in this MVP. Contact the appropriate local police or emergency "
        "service now, and tell them when and where the child was last seen."
    ),
    Intent.REGISTER_CHILD: (
        "Child registration is not available in this Wayfind MVP. Please do not "
        "share a child's private details here for registration."
    ),
    Intent.SHELTER_SEARCH: (
        "Wayfind cannot verify or recommend a shelter in this MVP. If you are "
        "with an unaccompanied child, contact the appropriate local child-protection "
        "authority or police for safe placement guidance."
    ),
}


def deferred_feature(state: WayfindState) -> dict:
    message = _DEFERRED_MESSAGES.get(state.get("intent"), "That feature is unavailable in this MVP.")
    return {
        "agent_events": state.get("agent_events", []) + [
            {"type": "assistant_message", "content": message}
        ],
        "final_response": message,
    }
