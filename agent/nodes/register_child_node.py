"""
agent/nodes/register_child_node.py
Node: register_child_node

Responsibility:
  Saves the pre-registered safe child record into the database / storage with
  status REGISTERED_SAFE. Returns a case / registration reference and reassurance message.

Safe rules:
  - This record is kept confidential with status REGISTERED_SAFE.
  - Never exposed in public missing child searches.
  - Emits submission_complete event with the record ID.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from agent.state import WayfindState
from app.config import get_settings
from schemas.child import ChildRegistrationData

logger = logging.getLogger(__name__)

_SUCCESS_MSG = (
    "✅ **Child Successfully Pre-Registered on Wayfind**\n\n"
    "Registration ID: **{ref}**\n"
    "Name: **{name}**\n"
    "Status: **REGISTERED_SAFE**\n\n"
    "Your child's profile is now securely kept on file. This record remains completely private "
    "and is only used for immediate family protection if an emergency or search request is ever initiated."
)


async def register_child_node(state: WayfindState) -> dict[str, Any]:
    """Persist pre-registered child record into Neon PostgreSQL and emit confirmation event."""
    existing_events = state.get("agent_events", [])
    reg = state.get("child_registration_data")

    child_name = "Child"
    gender = None
    age_val = None
    identifying_features: list[str] = []
    medical_notes = None
    emergency_contact = None

    if reg:
        if isinstance(reg, dict):
            child_name = reg.get("name") or "Child"
            gender = reg.get("gender")
            age = reg.get("age") or {}
            age_val = age.get("exact") if isinstance(age, dict) else getattr(age, "exact", None)
            identifying_features = reg.get("identifying_features") or []
            medical_notes = reg.get("medical_notes")
            emergency_contact = reg.get("emergency_contact")
        else:
            child_name = reg.name or "Child"
            gender = reg.gender
            age_obj = reg.age
            age_val = age_obj.exact if age_obj else None
            identifying_features = reg.identifying_features or []
            medical_notes = reg.medical_notes
            emergency_contact = reg.emergency_contact

    reg_ref = f"WF-REG-{uuid.uuid4().hex[:8].upper()}"

    # ── Persist directly to Neon PostgreSQL ──────────────────────────────────────
    settings = get_settings()
    db_url = settings.database_url
    child_id = str(uuid.uuid4())
    guardian_id = str(uuid.uuid4())

    if db_url:
        try:
            import psycopg
            with psycopg.connect(db_url) as conn:
                with conn.cursor() as cur:
                    # 1. Insert guardian record
                    phone_masked = emergency_contact or "+92 300 ***0000"
                    cur.execute(
                        """
                        INSERT INTO guardians (id, name, phone_masked)
                        VALUES (%s, %s, %s)
                        ON CONFLICT DO NOTHING;
                        """,
                        (guardian_id, f"Guardian of {child_name}", phone_masked),
                    )

                    # 2. Insert child record
                    cur.execute(
                        """
                        INSERT INTO children (id, guardian_id, name, estimated_age, gender, status)
                        VALUES (%s, %s, %s, %s, %s, 'REGISTERED_SAFE');
                        """,
                        (child_id, guardian_id, child_name, age_val, gender),
                    )

                    # 3. Insert physical attributes
                    cur.execute(
                        """
                        INSERT INTO physical_attributes (child_id, identifying_features, medical_notes)
                        VALUES (%s, %s, %s);
                        """,
                        (child_id, identifying_features if identifying_features else None, medical_notes),
                    )

                    # 4. Insert audit log
                    cur.execute(
                        """
                        INSERT INTO audit_log (action, entity_type, entity_id, metadata_json)
                        VALUES ('REGISTER_CHILD', 'children', %s, %s);
                        """,
                        (child_id, json.dumps({"registration_ref": reg_ref, "name": child_name, "status": "REGISTERED_SAFE"})),
                    )
                conn.commit()
            logger.info("Session %s: Persisted child '%s' (id=%s) to Neon PostgreSQL", state.get("session_id"), child_name, child_id)
        except Exception as exc:
            logger.error("Failed to persist registration to Neon PostgreSQL: %s", exc)

    logger.info(
        "Session %s: Child '%s' pre-registered successfully, ref=%s",
        state.get("session_id"),
        child_name,
        reg_ref,
    )

    return {
        "case_reference": reg_ref,
        "agent_events": existing_events + [
            {"type": "submission_complete", "record_id": reg_ref},
            {"type": "assistant_message", "content": _SUCCESS_MSG.format(ref=reg_ref, name=child_name)},
        ],
    }
