"""
mcp_server/tools/get_guidance.py
FastMCP Tool 5: get_guidance

Retrieve guidance from the Wayfind knowledge base via RAG.
Topics: found_child | missing_child | shelter | safety | reporting | emergency
Falls back to static content if RAG is unavailable.
Never exposes Qdrant internals.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from schemas.guidance import GuidanceResult

logger = logging.getLogger(__name__)

_DEFAULT_GUIDANCE_MAP: dict[str, str] = {
    "found_child": (
        "• Stay with the child in a safe, public location.\n"
        "• Contact local police or child protection authorities immediately.\n"
        "• Do not share the child's photo or identity on personal social media accounts.\n"
        "• Comfort the child and wait for official child welfare personnel to arrive."
    ),
    "missing_child": (
        "• File an immediate report with the nearest police station (no waiting period is required for missing children).\n"
        "• Provide the latest clear photos and details on what they were wearing.\n"
        "• Keep your phone line clear and contact relatives/neighbours.\n"
        "• Submit the report to Wayfind to check against our authorized intake records."
    ),
    "shelter": (
        "• Use authorized child-intake shelters and government child welfare bureaus only.\n"
        "• Avoid taking unaccompanied children to unverified private facilities.\n"
        "• Always request official documentation and an intake receipt."
    ),
    "safety": (
        "• Never leave an unaccompanied child alone.\n"
        "• Always remain in well-lit, public spaces when waiting for authorities.\n"
        "• If medical attention is required, proceed to the nearest government emergency hospital."
    ),
}

_GENERIC_GUIDANCE = (
    "• If you have found an unaccompanied child, stay in a safe, public place and contact police immediately.\n"
    "• If your child is missing, file a police report and submit their physical description to Wayfind.\n"
    "• Authorized shelters and NGOs can be located via our search support directory."
)


@lru_cache(maxsize=1)
def _load_static_yaml() -> dict:
    yaml_path = os.path.normpath(
        os.path.join(os.path.dirname(__file__), "..", "..", "config", "static_guidance.yaml")
    )
    if os.path.exists(yaml_path):
        try:
            import yaml
            with open(yaml_path, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.debug("Failed to load static_guidance.yaml: %s", exc)
    return {}


async def get_guidance(
    query: str,
    topic: str | None = None,
) -> GuidanceResult:
    """Retrieve guidance from RAG or static knowledge base."""
    resolved_topic = (topic or "").strip().lower() or None
    logger.info("get_guidance called with query='%s', topic='%s'", query, resolved_topic)

    # 1. Try downstream RAG service client (wired in Phase 9)
    try:
        from services.rag_client import get_rag_client

        client = get_rag_client()
        if client is not None:
            return await client.query(query=query, topic=resolved_topic)
    except (ImportError, AttributeError, Exception) as exc:
        logger.debug("Downstream rag_client not active, using static guidance: %s", exc)

    # 2. Check static YAML if available
    yaml_data = _load_static_yaml()
    if resolved_topic and resolved_topic in yaml_data:
        topic_info = yaml_data[resolved_topic]
        if isinstance(topic_info, dict):
            text = topic_info.get("guidance", _DEFAULT_GUIDANCE_MAP.get(resolved_topic, _GENERIC_GUIDANCE))
            steps = topic_info.get("next_steps", ["Follow official safety guidance"])
            return GuidanceResult(
                guidance=text,
                next_steps=steps,
                topic=resolved_topic,
                is_static_fallback=True,
            )

    # 3. Use default guidance map
    text = _DEFAULT_GUIDANCE_MAP.get(resolved_topic or "", _GENERIC_GUIDANCE)
    next_steps = [
        "Follow recommended safety procedures",
        "Contact official child protection services if needed",
        "Keep documentation and case reference numbers ready",
    ]

    return GuidanceResult(
        guidance=text,
        next_steps=next_steps,
        topic=resolved_topic or "general",
        is_static_fallback=True,
    )
