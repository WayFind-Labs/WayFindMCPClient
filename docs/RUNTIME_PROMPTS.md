# Wayfind prototype runtime prompts

The active public journey is **found-child reporting in Karachi**. The two
“Coming soon” cards are disabled in the frontend and do not start an agent
conversation. They have no active scenario prompts in this prototype.

## Found-child role prompt

The full, versioned system prompt is
[`mcp_client/knowledge/found_child_guidance.md`](../mcp_client/knowledge/found_child_guidance.md)
(`found-child-intake-v5`). Its core role instruction is:

> You are Wayfind's found-child reporting assistant for Karachi. Your job is to
> help a finder keep the child safe, contact the appropriate authority promptly,
> and calmly collect a found-child report they can review and record. You are a
> supportive guide, not a dispatcher or a substitute for police or rescue.

The same prompt requires one manageable question per turn, short plain English,
unknown details to remain unknown, and no claim of filing until a submission
receipt exists. It supplies Karachi contact provenance and instructs the model
to refer to the visible call panel instead of inventing phone numbers.

`mcp_client/conversation_context.py` injects this asset as the first system
message for follow-up questions and contextual guidance. Each call adds a
second, task-specific system message, then bounded recent dialogue. The final
free-text response path uses the same context. Structured report extraction
has a separate field-extraction prompt that forbids invented facts.

## Intent classifier

`mcp_client/llm.py` sends a separate system prompt defining FOUND_CHILD,
MISSING_CHILD, REGISTER_CHILD, GUIDANCE, SHELTER_SEARCH, CASE_STATUS and UNKNOWN.
It tells the model that an answer about age, clothing, condition, location or
finder contact after a found-child question remains FOUND_CHILD. The state
machine also keeps an open found-child draft in that flow if classification
mistakes a short detail for a deferred scenario. Safety guidance questions can
still interrupt.

## Future scenarios

When missing-child search and advance registration are enabled, give each its
own versioned role guidance and evaluation before activating its landing card.
The current classifier's intent definitions do not make either service active.
