"""
app/session.py
Session store for WayfindState across conversation turns.

Two backends:
  - MemorySessionStore  — in-process dict, dev only (lost on restart)
  - RedisSessionStore   — Redis-backed, production-ready

The session store is initialised once at app startup via lifespan and
accessed via dependency injection (get_session_store).

Session data is serialised as JSON.  WayfindState TypedDict values must
therefore be JSON-serialisable (Pydantic models serialise via .model_dump()).

Session IDs are UUIDs (v4) generated server-side on the first request.
They are returned to the client in the X-Session-ID response header and
expected back in the X-Session-ID request header on subsequent turns.

TTL: sessions expire after SESSION_TTL_SECONDS of inactivity.
"""

from __future__ import annotations

import json
import logging
import uuid
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)

SESSION_TTL_SECONDS = 3600  # 1 hour of inactivity


# ── Abstract base ──────────────────────────────────────────────────────────────

class SessionStore(ABC):
    """Abstract session store interface."""

    @abstractmethod
    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Return the stored state dict, or None if the session does not exist."""

    @abstractmethod
    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        """Persist the state dict for the given session ID, resetting TTL."""

    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """Delete a session (e.g. after case closure)."""

    @abstractmethod
    async def close(self) -> None:
        """Clean up any open connections."""

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def new_session_id() -> str:
        """Generate a fresh UUID-based session ID."""
        return str(uuid.uuid4())


# ── In-memory backend (dev) ────────────────────────────────────────────────────

class MemorySessionStore(SessionStore):
    """Simple in-process dict store.

    NOT suitable for production:
      - State is lost on process restart.
      - No TTL enforcement (memory grows unbounded in long-running processes).

    Use only when SESSION_BACKEND=memory (local dev / CI tests).
    """

    def __init__(self) -> None:
        self._store: dict[str, dict[str, Any]] = {}

    async def get(self, session_id: str) -> dict[str, Any] | None:
        return self._store.get(session_id)

    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        self._store[session_id] = state

    async def delete(self, session_id: str) -> None:
        self._store.pop(session_id, None)

    async def close(self) -> None:
        self._store.clear()


# ── Redis backend (production) ─────────────────────────────────────────────────

class RedisSessionStore(SessionStore):
    """Redis-backed session store with TTL.

    Uses the async redis client (redis.asyncio).
    Connection is established lazily on first use after startup.
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: Any | None = None  # redis.asyncio.Redis

    async def _ensure_client(self) -> Any:
        if self._client is None:
            try:
                import redis.asyncio as aioredis  # type: ignore[import-untyped]
                self._client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                logger.info("Redis session store connected to %s", self._redis_url)
            except Exception as exc:
                logger.error("Failed to connect to Redis: %s", exc)
                raise
        return self._client

    def _key(self, session_id: str) -> str:
        return f"wayfind:session:{session_id}"

    async def get(self, session_id: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        raw = await client.get(self._key(session_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)  # type: ignore[no-any-return]
        except json.JSONDecodeError:
            logger.warning("Corrupted session data for %s — dropping session", session_id)
            await self.delete(session_id)
            return None

    async def set(self, session_id: str, state: dict[str, Any]) -> None:
        client = await self._ensure_client()
        await client.setex(
            self._key(session_id),
            SESSION_TTL_SECONDS,
            json.dumps(state, default=str),
        )

    async def delete(self, session_id: str) -> None:
        client = await self._ensure_client()
        await client.delete(self._key(session_id))

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("Redis session store connection closed")


# ── Factory ────────────────────────────────────────────────────────────────────

def create_session_store(backend: str, redis_url: str = "") -> SessionStore:
    """Instantiate the appropriate session store from config.

    Args:
        backend:   "memory" or "redis"
        redis_url: Redis connection URL (required when backend="redis")
    """
    if backend == "redis":
        if not redis_url:
            raise ValueError("REDIS_URL must be set when SESSION_BACKEND=redis")
        return RedisSessionStore(redis_url)
    return MemorySessionStore()
