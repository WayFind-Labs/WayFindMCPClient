"""
mcp_client/llm.py
LLM wrapper for Wayfind with typed, structured output via Pydantic models.

Supports:
  - Gemini via `langchain-google-genai` (default)
  - Extensible to other providers
  - Robust offline / fallback handling when API keys are not set

Safety & Extraction Rules:
  - NEVER invent or hallucinate fields that the user did not state.
  - Leave unknown fields None / empty.
  - Age: exact only when exact age given; min/max for approximations.
  - Safe language: Never state confirmed identity, never use internal scores.
"""

from __future__ import annotations

import contextlib
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from agent.state import Intent, WayfindState
from schemas.child import AgeRange, ChildSearchCriteria, FoundChildReport, HeightRange

logger = logging.getLogger(__name__)

# Pattern to extract case reference from text (e.g. WF-20260925-0042)
_CASE_REF_REGEX = re.compile(r"\bWF-\d{8}-\d{4}\b", re.IGNORECASE)


class IntentResult(BaseModel):
    """Structured result returned by extract_intent."""

    intent: Intent = Field(
        default=Intent.UNKNOWN,
        description="Classified user intent enum.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Classification confidence score from 0.0 to 1.0.",
    )
    case_reference: str | None = Field(
        default=None,
        description="Extracted case reference (e.g., WF-20260925-0042) if user asked about status.",
    )
    reasoning: str | None = Field(
        default=None,
        description="Brief justification for the classified intent.",
    )


class _ChildCriteriaLLM(BaseModel):
    """Internal model for structured LLM extraction of search criteria."""

    gender: str | None = Field(
        default=None,
        description="Gender: 'male' | 'female' | 'other' | None if not mentioned.",
    )
    age_exact: int | None = Field(
        default=None,
        description="Exact age in years if explicitly stated.",
    )
    age_min: int | None = Field(
        default=None,
        description="Minimum age in years if approximate (e.g. 'around 5 or 6' -> min 4 or 5).",
    )
    age_max: int | None = Field(
        default=None,
        description="Maximum age in years if approximate.",
    )
    height_min: int | None = Field(
        default=None,
        description="Minimum height in cm if approximate.",
    )
    height_max: int | None = Field(
        default=None,
        description="Maximum height in cm if approximate.",
    )
    height_exact: int | None = Field(
        default=None,
        description="Exact height in cm if stated.",
    )
    last_seen_location: str | None = Field(
        default=None,
        description="City, area, or landmark where the child was last seen.",
    )
    last_seen_date: str | None = Field(
        default=None,
        description="Date or relative time when last seen (e.g., 'yesterday', '2026-09-24').",
    )
    clothing: list[str] = Field(
        default_factory=list,
        description="Distinct clothing items described (e.g., ['blue t-shirt', 'black shorts']).",
    )
    physical_features: list[str] = Field(
        default_factory=list,
        description="Distinct physical features (e.g., ['scar on left cheek', 'curly hair']).",
    )
    hair_color: str | None = Field(
        default=None,
        description="Hair colour (e.g., 'black', 'brown').",
    )
    eye_color: str | None = Field(
        default=None,
        description="Eye colour (e.g., 'brown', 'black').",
    )
    identifying_marks: list[str] = Field(
        default_factory=list,
        description="Birthmarks, scars, tattoos, or other distinctive marks.",
    )


class _FoundChildLLM(BaseModel):
    """Internal model for structured LLM extraction of a found child report."""

    gender: str | None = Field(
        default=None,
        description="Estimated gender: 'male' | 'female' | 'unknown' | None.",
    )
    approximate_age: int | None = Field(
        default=None,
        description="Estimated age in years if described.",
    )
    found_location: str | None = Field(
        default=None,
        description="Where the child was found (street, landmark, city).",
    )
    found_date: str | None = Field(
        default=None,
        description="When the child was found (e.g., 'today', '2 hours ago').",
    )
    clothing_description: str | None = Field(
        default=None,
        description="Detailed description of what the child was wearing.",
    )
    physical_condition: str | None = Field(
        default=None,
        description="Physical condition (e.g., 'healthy', 'minor scratches', 'distressed').",
    )
    distinguishing_features: list[str] = Field(
        default_factory=list,
        description="Any distinguishing physical features.",
    )
    current_status: str | None = Field(
        default=None,
        description="Where the child is right now (e.g., 'with reporter at police station').",
    )


class WayfindLLM:
    """Provider-agnostic LLM interface for Wayfind.

    Configured with Gemini by default via langchain-google-genai.
    Falls back gracefully if no API key is set or on API unavailability.
    """

    def __init__(
        self,
        provider: str = "groq",
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.api_key = api_key or ""
        # Default model per provider
        if model:
            self.model_name = model
        elif self.provider == "groq":
            self.model_name = "llama-3.3-70b-versatile"
        elif self.provider == "gemini":
            self.model_name = "gemini-3.8-flash"
        else:
            self.model_name = "gpt-4o-mini"
        self._llm: Any | None = None

        if self.api_key:
            self._init_client()
        else:
            logger.info("WayfindLLM initialised in heuristic fallback mode (no API key provided)")

    def _init_client(self) -> None:
        """Initialise the underlying LangChain chat model."""
        try:
            if self.provider == "groq":
                from langchain_groq import ChatGroq

                self._llm = ChatGroq(
                    model=self.model_name,
                    groq_api_key=self.api_key,
                    temperature=0.1,
                )
                logger.info("ChatGroq model '%s' initialised", self.model_name)
            elif self.provider == "gemini":
                from langchain_google_genai import ChatGoogleGenerativeAI

                self._llm = ChatGoogleGenerativeAI(
                    model=self.model_name,
                    google_api_key=self.api_key,
                    temperature=0.1,
                )
                logger.info("ChatGoogleGenerativeAI model '%s' initialised", self.model_name)
            else:
                logger.warning("Unsupported LLM provider '%s', using fallback mode", self.provider)
        except Exception as exc:
            logger.warning("Failed to initialise LLM provider %s: %s", self.provider, exc)
            self._llm = None

    # ── Intent Extraction ──────────────────────────────────────────────────────

    async def extract_intent(
        self,
        conversation_history: list[dict],
        prompt: str,
    ) -> IntentResult:
        """Extract user intent using structured output."""
        # 1. Try structured output with LLM if available
        if self._llm is not None:
            try:
                system_prompt = (
                    "You are the intent classifier for Wayfind, a platform assisting with children welfare.\n"
                    "Classify the user message into one of these intents:\n"
                    "- REGISTER_CHILD: Guardian is pre-registering a safe child on Wayfind for peacetime protection.\n"
                    "- MISSING_CHILD: User is reporting a missing child or searching for their lost child.\n"
                    "- FOUND_CHILD: User has found an unaccompanied/lost child and wants to report them.\n"
                    "- SHELTER_SEARCH: User is looking for authorized child shelters, NGOs, or intake facilities.\n"
                    "- GUIDANCE: User is asking general advice, safety tips, or procedures.\n"
                    "- CASE_STATUS: User wants to check the status of an existing case / report.\n"
                    "- UNKNOWN: Irrelevant, ambiguous, or general greeting.\n\n"
                    "If the user mentions a case reference number (like WF-20260925-0042), extract it into case_reference.\n"
                    "Provide a confidence score between 0.0 and 1.0."
                )

                structured_llm = self._llm.with_structured_output(IntentResult)
                messages = [{"role": "system", "content": system_prompt}]
                for msg in conversation_history[-4:]:
                    content = getattr(msg, "content", "") if not isinstance(msg, dict) else msg.get("content", "")
                    role = getattr(msg, "type", "user") if not isinstance(msg, dict) else msg.get("role", "user")
                    if role == "human":
                        role = "user"
                    elif role == "ai":
                        role = "assistant"
                    messages.append({"role": role, "content": str(content)})
                messages.append({"role": "user", "content": prompt})

                result: IntentResult = await structured_llm.ainvoke(messages)
                return result
            except Exception as exc:
                logger.warning("LLM extract_intent call failed, falling back to heuristics: %s", exc)

        # 2. Heuristic fallback
        return self._heuristic_extract_intent(conversation_history, prompt)

    def _heuristic_extract_intent(
        self,
        conversation_history: list[Any],
        prompt: str,
    ) -> IntentResult:
        """Heuristic intent classifier fallback."""
        text_lower = prompt.lower()
        history_texts: list[str] = []
        for m in conversation_history:
            content = getattr(m, "content", None) if not isinstance(m, dict) else m.get("content")
            role = getattr(m, "type", None) if not isinstance(m, dict) else m.get("role")
            if (role in ("user", "human") or role is None) and content:
                history_texts.append(str(content).lower())
        all_text = text_lower + " " + " ".join(history_texts)

        if any(w in all_text for w in ["register my child", "register a child", "pre-register", "add my child", "register on wayfind", "child registration", "i want to register"]):
            return IntentResult(
                intent=Intent.REGISTER_CHILD,
                confidence=0.90,
                reasoning="Child registration intent detected",
            )

        case_match = _CASE_REF_REGEX.search(prompt)
        if case_match:
            return IntentResult(
                intent=Intent.CASE_STATUS,
                confidence=0.85,
                case_reference=case_match.group(0),
                reasoning="Case reference format detected in user message",
            )

        if any(w in all_text for w in ["found", "found a child", "found a boy", "found a girl", "unaccompanied", "saw a kid alone"]):
            return IntentResult(
                intent=Intent.FOUND_CHILD,
                confidence=0.75,
                reasoning="Found-child keywords detected",
            )

        if any(w in all_text for w in ["missing", "lost", "looking for", "searching for", "my son", "my daughter", "my child", "disappeared"]):
            return IntentResult(
                intent=Intent.MISSING_CHILD,
                confidence=0.75,
                reasoning="Missing-child keywords detected",
            )


        if any(w in all_text for w in ["shelter", "ngo", "police station", "hospital", "where can i take", "intake centre", "safe place"]):
            return IntentResult(
                intent=Intent.SHELTER_SEARCH,
                confidence=0.70,
                reasoning="Shelter search keywords detected",
            )

        if any(w in all_text for w in ["what should i do", "how do i", "guide", "help me understand", "procedure", "steps", "advice"]):
            return IntentResult(
                intent=Intent.GUIDANCE,
                confidence=0.65,
                reasoning="Guidance keywords detected",
            )

        return IntentResult(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            reasoning="Could not confidently classify intent",
        )

    # ── Child Criteria Extraction ─────────────────────────────────────────────

    async def extract_child_criteria(
        self,
        existing_criteria: ChildSearchCriteria | None,
        prompt: str,
        form_data: dict | None = None,
    ) -> ChildSearchCriteria:
        """Merge-extract missing child criteria from prompt and optional form_data.

        Strictly enforces: never invent unstated values.
        """
        # Start with a copy of existing criteria or default
        if existing_criteria is None:
            current = ChildSearchCriteria()
        elif isinstance(existing_criteria, dict):
            current = ChildSearchCriteria(**existing_criteria)
        else:
            current = existing_criteria.model_copy()

        # Merge form_data if provided
        if form_data:
            current = self._merge_form_data_missing(current, form_data)

        # If LLM available, extract from free-text prompt
        if self._llm is not None and prompt.strip():
            try:
                system_prompt = (
                    "Extract structured physical and contextual criteria about a MISSING child from the user's message.\n"
                    "CRITICAL RULES:\n"
                    "1. DO NOT invent or assume any values not explicitly stated.\n"
                    "2. Leave fields None or empty if not mentioned.\n"
                    "3. If approximate age is stated (e.g. 'around 7'), set age_min=6, age_max=8.\n"
                    "4. If exact age is given (e.g. '7 years old'), set age_exact=7."
                )

                structured_llm = self._llm.with_structured_output(_ChildCriteriaLLM)
                extracted: _ChildCriteriaLLM = await structured_llm.ainvoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ])

                # Merge extracted LLM fields into current criteria
                updates: dict[str, Any] = {}
                if extracted.gender and not current.gender:
                    updates["gender"] = extracted.gender.lower()

                # Age
                if extracted.age_exact is not None or extracted.age_min is not None or extracted.age_max is not None:
                    updates["age"] = AgeRange(
                        exact=extracted.age_exact or current.age.exact,
                        min=extracted.age_min or current.age.min,
                        max=extracted.age_max or current.age.max,
                    )

                # Height
                if extracted.height_exact is not None or extracted.height_min is not None or extracted.height_max is not None:
                    updates["height"] = HeightRange(
                        exact=extracted.height_exact or current.height.exact,
                        min=extracted.height_min or current.height.min,
                        max=extracted.height_max or current.height.max,
                    )

                if extracted.last_seen_location and not current.last_seen_location:
                    updates["last_seen_location"] = extracted.last_seen_location

                if extracted.last_seen_date and not current.last_seen_date:
                    updates["last_seen_date"] = extracted.last_seen_date

                if extracted.hair_color and not current.hair_color:
                    updates["hair_color"] = extracted.hair_color

                if extracted.eye_color and not current.eye_color:
                    updates["eye_color"] = extracted.eye_color

                if extracted.clothing:
                    combined_clothing = list(dict.fromkeys(current.clothing + extracted.clothing))
                    updates["clothing"] = combined_clothing

                if extracted.physical_features:
                    combined_features = list(dict.fromkeys(current.physical_features + extracted.physical_features))
                    updates["physical_features"] = combined_features

                if extracted.identifying_marks:
                    combined_marks = list(dict.fromkeys(current.identifying_marks + extracted.identifying_marks))
                    updates["identifying_marks"] = combined_marks

                if updates:
                    current = current.model_copy(update=updates)
                return current
            except Exception as exc:
                logger.warning("LLM extract_child_criteria failed, falling back to heuristics: %s", exc)

        # Fallback heuristic merge
        return self._heuristic_merge_missing(current, prompt)

    def _merge_form_data_missing(
        self,
        current: ChildSearchCriteria,
        form_data: dict,
    ) -> ChildSearchCriteria:
        """Merge explicit form_data dictionary."""
        updates: dict[str, Any] = {}

        if "gender" in form_data and form_data["gender"]:
            updates["gender"] = str(form_data["gender"]).lower()

        if "age" in form_data and form_data["age"] is not None:
            with contextlib.suppress(ValueError, TypeError):
                updates["age"] = AgeRange(exact=int(form_data["age"]))

        if "last_seen_location" in form_data and form_data["last_seen_location"]:
            updates["last_seen_location"] = str(form_data["last_seen_location"])
        elif "location" in form_data and form_data["location"]:
            updates["last_seen_location"] = str(form_data["location"])

        if "clothing" in form_data and form_data["clothing"]:
            clothing_val = form_data["clothing"]
            if isinstance(clothing_val, str):
                updates["clothing"] = [clothing_val]
            elif isinstance(clothing_val, list):
                updates["clothing"] = clothing_val

        return current.model_copy(update=updates) if updates else current

    def _heuristic_merge_missing(
        self,
        current: ChildSearchCriteria,
        prompt: str,
    ) -> ChildSearchCriteria:
        """Rule-based extractor for when LLM is unavailable."""
        prompt_lower = prompt.lower()
        updates: dict[str, Any] = {}

        if not current.gender:
            if re.search(r"\b(girl|daughter|female|she|her)\b", prompt_lower):
                updates["gender"] = "female"
            elif re.search(r"\b(boy|son|male|he|his|him)\b", prompt_lower):
                updates["gender"] = "male"

        if not (current.age.exact or current.age.min or current.age.max):
            age_match = re.search(r"\b(?:age\s*)?(\d{1,2})\s*(?:years?\s*old|yo|yr|yrs)?\b", prompt_lower)
            if age_match:
                try:
                    val = int(age_match.group(1))
                    if 0 <= val <= 18:
                        updates["age"] = AgeRange(exact=val)
                except (ValueError, IndexError):
                    pass

        if not current.last_seen_location:
            loc_match = re.search(r"(?:last seen at|near|in|at)\s+([a-zA-Z0-9\s,]+?)(?:\.|\band\b|$)", prompt, re.IGNORECASE)
            if loc_match:
                candidate = loc_match.group(1).strip()
                if len(candidate) > 2:
                    updates["last_seen_location"] = candidate

        return current.model_copy(update=updates) if updates else current

    # ── Found Child Extraction ────────────────────────────────────────────────

    async def extract_found_child_report(
        self,
        existing_report: FoundChildReport | None,
        prompt: str,
        form_data: dict | None = None,
        media_reference: str | None = None,
    ) -> FoundChildReport:
        """Merge-extract found child report from prompt, form_data, and media."""
        if existing_report is None:
            current = FoundChildReport(found_location="unknown")
        elif isinstance(existing_report, dict):
            current = FoundChildReport(**existing_report)
        else:
            current = existing_report.model_copy()

        updates: dict[str, Any] = {}
        if media_reference and not current.media_reference:
            updates["media_reference"] = media_reference

        if form_data:
            if "gender" in form_data and form_data["gender"]:
                updates["gender"] = str(form_data["gender"]).lower()
            if "location" in form_data and form_data["location"]:
                updates["found_location"] = str(form_data["location"])
            elif "found_location" in form_data and form_data["found_location"]:
                updates["found_location"] = str(form_data["found_location"])
            if "approximate_age" in form_data and form_data["approximate_age"]:
                with contextlib.suppress(ValueError, TypeError):
                    updates["approximate_age"] = int(form_data["approximate_age"])

        if updates:
            current = current.model_copy(update=updates)

        if self._llm is not None and prompt.strip():
            try:
                system_prompt = (
                    "Extract details about a FOUND unaccompanied child from the user's message.\n"
                    "CRITICAL RULES:\n"
                    "1. DO NOT invent or assume any values not explicitly stated.\n"
                    "2. Leave fields None if not mentioned.\n"
                    "3. Extract found_location if a location is described."
                )

                structured_llm = self._llm.with_structured_output(_FoundChildLLM)
                extracted: _FoundChildLLM = await structured_llm.ainvoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ])

                llm_updates: dict[str, Any] = {}
                if extracted.gender and not current.gender:
                    llm_updates["gender"] = extracted.gender.lower()
                if extracted.approximate_age and not current.approximate_age:
                    llm_updates["approximate_age"] = extracted.approximate_age
                if extracted.found_location and (not current.found_location or current.found_location == "unknown"):
                    llm_updates["found_location"] = extracted.found_location
                if extracted.found_date and not current.found_date:
                    llm_updates["found_date"] = extracted.found_date
                if extracted.clothing_description and not current.clothing_description:
                    llm_updates["clothing_description"] = extracted.clothing_description
                if extracted.physical_condition and not current.physical_condition:
                    llm_updates["physical_condition"] = extracted.physical_condition
                if extracted.distinguishing_features:
                    llm_updates["distinguishing_features"] = list(dict.fromkeys(
                        current.distinguishing_features + extracted.distinguishing_features
                    ))
                if extracted.current_status and not current.current_status:
                    llm_updates["current_status"] = extracted.current_status

                if llm_updates:
                    current = current.model_copy(update=llm_updates)
                return current
            except Exception as exc:
                logger.warning("LLM extract_found_child_report failed, falling back: %s", exc)

        # Fallback heuristic
        return self._heuristic_merge_found(current, prompt)

    def _heuristic_merge_found(
        self,
        current: FoundChildReport,
        prompt: str,
    ) -> FoundChildReport:
        """Rule-based extractor for found child reports."""
        prompt_lower = prompt.lower()
        updates: dict[str, Any] = {}

        if not current.gender:
            if re.search(r"\b(girl|female|she|her)\b", prompt_lower):
                updates["gender"] = "female"
            elif re.search(r"\b(boy|male|he|his|him)\b", prompt_lower):
                updates["gender"] = "male"

        if current.found_location == "unknown" or not current.found_location:
            loc_match = re.search(r"(?:found at|near|in|at)\s+([a-zA-Z0-9\s,]+?)(?:\.|\band\b|$)", prompt, re.IGNORECASE)
            if loc_match:
                candidate = loc_match.group(1).strip()
                if len(candidate) > 2:
                    updates["found_location"] = candidate

        return current.model_copy(update=updates) if updates else current

    # ── Follow-up Question Generation ─────────────────────────────────────────

    async def generate_followup_question(
        self,
        missing_fields: list[str],
        context: list[dict] | None = None,
    ) -> str:
        """Generate an empathetic, concise natural-language follow-up question."""
        if not missing_fields:
            return "Could you provide any additional details?"

        field_labels = {
            "name": "the child's full name",
            "gender": "the child's gender",
            "age": "approximately how old the child is",
            "city": "your home city or area",
            "identifying_features": "any distinguishing physical features or birthmarks",
            "medical_notes": "any medical conditions or allergy notes",
            "emergency_contact": "an emergency contact phone number",
            "last_seen_location": "where the child was last seen",
            "found_location": "where the child was found",
            "clothing": "what clothing the child was wearing",
            "hair_color": "the child's hair colour",
        }

        if self._llm is not None:
            try:
                labels = [field_labels.get(f, f.replace("_", " ")) for f in missing_fields[:2]]
                prompt = (
                    f"Ask the user gently and empathetically for these missing details: {', '.join(labels)}.\n"
                    "Keep the question short (1-2 sentences), caring, and clear. Never be robotic."
                )
                response = await self._llm.ainvoke([
                    {"role": "system", "content": "You are a caring assistant helping a user report or search for a child."},
                    {"role": "user", "content": prompt},
                ])
                content = getattr(response, "content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            except Exception as exc:
                logger.warning("LLM generate_followup_question failed: %s", exc)

        # Fallback template
        labels = [field_labels.get(f, f.replace("_", " ")) for f in missing_fields[:2]]
        if len(labels) == 1:
            return f"Could you please tell me {labels[0]}?"
        return f"Could you please tell me {labels[0]} and {labels[1]}?"

    # ── Final Response Generation ─────────────────────────────────────────────

    async def generate_final_response(self, state: WayfindState) -> str:
        """Generate a safe, empathetic natural language response from state."""
        intent = state.get("intent")
        events = state.get("agent_events", [])

        # Check if an event already has content
        for evt in reversed(events):
            if evt.get("type") == "assistant_message" and evt.get("content"):
                return str(evt["content"])

        if self._llm is not None:
            try:
                system_prompt = (
                    "You are the Wayfind support assistant helping someone during a missing or found child event.\n"
                    "SAFETY & TONE RULES:\n"
                    "1. Always be empathetic, calm, and supportive.\n"
                    "2. NEVER say 'we found your child' or confirm an identity — all matches require official verification.\n"
                    "3. NEVER reveal internal match scores, algorithms, or technical IDs.\n"
                    "4. Summarise the next steps clearly."
                )
                summary = f"Intent: {intent.value if intent else 'unknown'}. Recent events count: {len(events)}."
                response = await self._llm.ainvoke([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Provide a brief, reassuring closing message based on this session state: {summary}"},
                ])
                content = getattr(response, "content", "")
                if isinstance(content, str) and content.strip():
                    return content.strip()
            except Exception as exc:
                logger.warning("LLM generate_final_response failed: %s", exc)

        return (
            "Thank you for reaching out to Wayfind. We have recorded your information and "
            "our team will take the appropriate next steps. If you have any new details, please share them."
        )
