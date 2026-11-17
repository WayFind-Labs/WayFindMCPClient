"""Packaged runtime knowledge for user-facing LLM turns (not a developer skill)."""

from functools import lru_cache
from importlib.resources import files
from typing import Any


@lru_cache(maxsize=1)
def load_conversation_guidance() -> str:
    """Read the versioned asset independently of the process working directory.

    Missing/empty content raises instead of silently sending an ungrounded prompt.
    Restart the agent after editing the asset to reload the cached policy.
    """
    content = (
        files("mcp_client")
        .joinpath("knowledge", "found_child_guidance.md")
        .read_text(encoding="utf-8")
        .strip()
    )
    if not content:
        raise ValueError("Found-child conversation guidance is empty")
    return content


def conversation_messages(
    task: str, history: list[Any] | None = None, prompt: str | None = None
) -> list[dict[str, str]]:
    """Keep policy privileged and only user/assistant dialogue in bounded history."""
    messages = [
        {"role": "system", "content": load_conversation_guidance()},
        {"role": "system", "content": task},
    ]
    for item in (history or [])[-8:]:
        if isinstance(item, dict):
            role = item.get("role") or item.get("type")
            content = item.get("content")
        else:
            role = getattr(item, "type", None)
            content = getattr(item, "content", None)
        role = {"human": "user", "ai": "assistant"}.get(role, role)
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content[:4000]})
    if prompt and (messages[-1]["role"] != "user" or messages[-1]["content"] != prompt):
        messages.append({"role": "user", "content": prompt[:4000]})
    return messages


# Explicit degraded UI guidance; this is not a regex/keyword conversation engine.
UNAVAILABLE_GUIDANCE = (
    "The conversational assistant is unavailable right now. "
    "If you have found a child, stay nearby in a safe, visible public place. "
    "Do not take them home or into a private vehicle, share their photo or location "
    "publicly, or hand them to an unverified person. Contact local police or "
    "child-protection services directly; seek emergency medical help if needed. "
    "This guidance does not mean a report has been saved or anyone notified."
)
