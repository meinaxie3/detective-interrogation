"""
session_store.py — Pluggable session backing store.

Phase 1: InMemoryStore (module-level dict — fast, lost on restart)
Phase 2: RedisStore    (persistent, TTL-aware, multi-process safe)

The active store is selected at startup from Settings.redis_url:
  - REDIS_URL set in backend/.env → RedisStore
  - REDIS_URL unset              → InMemoryStore (default)

Redis key schema:
  session:{session_id}              → GameSessionModel JSON
  memory:{session_id}:{suspect_id}  → JSON list of {role, content} dicts

Backward-compatible API:
  get_store()  → returns the singleton AbstractSessionStore
  clear()      → sync reset for tests (InMemoryStore only)
"""

import json
from abc import ABC, abstractmethod
from typing import Optional


# ── Abstract interface ────────────────────────────────────────────────────────

class AbstractSessionStore(ABC):
    """Common async interface for all session store implementations."""

    @abstractmethod
    async def session_exists(self, session_id: str) -> bool:
        """Return True if the session is present (and not expired in Redis)."""

    @abstractmethod
    async def get_session_data(self, session_id: str) -> Optional[dict]:
        """Return the raw session dict or None if missing/expired."""

    @abstractmethod
    async def set_session_data(self, session_id: str, data: dict) -> None:
        """Create or overwrite a session. Resets TTL in Redis."""

    @abstractmethod
    async def get_memories(self, session_id: str, suspect_id: str) -> list[dict]:
        """Return all messages for one suspect (empty list if none yet)."""

    @abstractmethod
    async def append_memory(
        self, session_id: str, suspect_id: str, msg: dict
    ) -> None:
        """Append one {role, content} message to a suspect's memory."""

    @abstractmethod
    async def clear(self) -> None:
        """Wipe all data. Use only in tests."""


# ── In-memory implementation ──────────────────────────────────────────────────

class InMemoryStore(AbstractSessionStore):
    """
    Phase 1 / fallback store. Data lives only for the process lifetime.
    Thread-safe for a single uvicorn worker (GIL protects simple dict ops).
    Not suitable for multi-worker production — use RedisStore instead.

    Internal layout:
      _data[session_id] = {
          "session":  dict,                       # serialised GameSessionModel
          "memories": { suspect_id: [msg, ...] }  # per-suspect chat history
      }
    """

    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    async def session_exists(self, session_id: str) -> bool:
        return session_id in self._data

    async def get_session_data(self, session_id: str) -> Optional[dict]:
        entry = self._data.get(session_id)
        return entry["session"] if entry else None

    async def set_session_data(self, session_id: str, data: dict) -> None:
        if session_id in self._data:
            self._data[session_id]["session"] = data
        else:
            self._data[session_id] = {"session": data, "memories": {}}

    async def get_memories(self, session_id: str, suspect_id: str) -> list[dict]:
        entry = self._data.get(session_id)
        if not entry:
            return []
        return list(entry["memories"].get(suspect_id, []))

    async def append_memory(
        self, session_id: str, suspect_id: str, msg: dict
    ) -> None:
        memories = self._data[session_id]["memories"]
        if suspect_id not in memories:
            memories[suspect_id] = []
        memories[suspect_id].append(msg)

    async def clear(self) -> None:
        self._data.clear()

    def clear_sync(self) -> None:
        """Synchronous reset used by pytest fixtures that cannot be async."""
        self._data.clear()


# ── Redis implementation ──────────────────────────────────────────────────────

class RedisStore(AbstractSessionStore):
    """
    Phase 2 store backed by Redis.

    All keys are written with an expiry (default 2 h) so abandoned games
    clean themselves up automatically. Requires redis>=5.0 and a running
    Redis instance.  Set REDIS_URL in backend/.env to enable.
    """

    def __init__(self, redis_url: str, ttl: int = 7200) -> None:
        import redis.asyncio as aioredis
        self._redis = aioredis.from_url(redis_url, decode_responses=True)
        self._ttl = ttl

    # ── Key helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _session_key(session_id: str) -> str:
        return f"session:{session_id}"

    @staticmethod
    def _memory_key(session_id: str, suspect_id: str) -> str:
        return f"memory:{session_id}:{suspect_id}"

    # ── Interface ─────────────────────────────────────────────────────────────

    async def session_exists(self, session_id: str) -> bool:
        return bool(await self._redis.exists(self._session_key(session_id)))

    async def get_session_data(self, session_id: str) -> Optional[dict]:
        raw = await self._redis.get(self._session_key(session_id))
        return json.loads(raw) if raw is not None else None

    async def set_session_data(self, session_id: str, data: dict) -> None:
        await self._redis.set(
            self._session_key(session_id),
            json.dumps(data),
            ex=self._ttl,
        )

    async def get_memories(self, session_id: str, suspect_id: str) -> list[dict]:
        raw = await self._redis.get(self._memory_key(session_id, suspect_id))
        return json.loads(raw) if raw is not None else []

    async def append_memory(
        self, session_id: str, suspect_id: str, msg: dict
    ) -> None:
        key = self._memory_key(session_id, suspect_id)
        existing_raw = await self._redis.get(key)
        existing: list[dict] = json.loads(existing_raw) if existing_raw else []
        existing.append(msg)
        await self._redis.set(key, json.dumps(existing), ex=self._ttl)

    async def clear(self) -> None:
        """Flush the entire Redis DB. Test use only — never call in production."""
        await self._redis.flushdb()

    async def close(self) -> None:
        """Cleanly close the Redis connection (use in app shutdown handler)."""
        await self._redis.aclose()


# ── Singleton factory ─────────────────────────────────────────────────────────

_store: Optional[AbstractSessionStore] = None


def get_store() -> AbstractSessionStore:
    """
    Return the active session store singleton.
    Initialised once on first call; subsequent calls return the same instance.
    Store type is selected by Settings.redis_url.
    """
    global _store
    if _store is None:
        from app.core.config import settings
        if settings.redis_url:
            _store = RedisStore(settings.redis_url, ttl=settings.session_ttl_seconds)
        else:
            _store = InMemoryStore()
    return _store


def reset_store_instance() -> None:
    """
    Force re-initialisation of the store singleton.
    Use in tests that need to switch between InMemory and Redis implementations.
    """
    global _store
    _store = None


def clear() -> None:
    """
    Synchronously reset the store to empty — for test fixtures only.
    Works only with InMemoryStore.  For Redis, call: await get_store().clear()
    """
    store = get_store()
    if isinstance(store, InMemoryStore):
        store.clear_sync()
    else:
        raise RuntimeError(
            "clear() is only supported for InMemoryStore. "
            "Use 'await get_store().clear()' in async Redis test fixtures."
        )
