"""
session_service.py — Read/write game sessions through the abstract store.

Phase 2: backed by AbstractSessionStore (InMemoryStore or RedisStore).
The public interface is identical to Phase 1 — only the backing store changes.
Routes and agents import this module; they never touch the store directly.

Redis key schema (handled inside session_store.py):
  session:{session_id}              → GameSessionModel JSON
  memory:{session_id}:{suspect_id}  → JSON list of {role, content} dicts
"""

from app.models.session import GameSessionModel, ExtractedClue
from app.core.session_store import get_store


# ── Core session CRUD ─────────────────────────────────────────────────────────

async def create(session: GameSessionModel) -> None:
    """Persist a new session. Overwrites if session_id already exists."""
    await get_store().set_session_data(
        session.session_id,
        session.model_dump(mode="json"),
    )


async def get(session_id: str) -> GameSessionModel:
    """
    Retrieve and deserialise a session.
    Raises KeyError if the session does not exist (or has expired in Redis).
    """
    data = await get_store().get_session_data(session_id)
    if data is None:
        raise KeyError(f"Session '{session_id}' not found or expired")
    return GameSessionModel(**data)


async def update(session: GameSessionModel) -> None:
    """
    Overwrite an existing session.
    Raises KeyError if the session is missing (prevents silent data loss).
    """
    store = get_store()
    if not await store.session_exists(session.session_id):
        raise KeyError(f"Session '{session.session_id}' not found")
    await store.set_session_data(
        session.session_id,
        session.model_dump(mode="json"),
    )


# ── Conversation memory ───────────────────────────────────────────────────────

async def append_message(
    session_id: str,
    suspect_id: str,
    role: str,
    content: str,
) -> None:
    """
    Append one message to a suspect's conversation memory.
    role must be 'user' or 'assistant'.
    Creates the suspect's memory list if it doesn't exist yet.
    """
    if role not in ("user", "assistant"):
        raise ValueError(f"role must be 'user' or 'assistant', got '{role}'")

    store = get_store()
    if not await store.session_exists(session_id):
        raise KeyError(f"Session '{session_id}' not found")

    await store.append_memory(session_id, suspect_id, {"role": role, "content": content})


async def get_messages(session_id: str, suspect_id: str) -> list[dict]:
    """
    Return the full conversation history for one suspect.
    Returns an empty list if the suspect has not been questioned yet.
    Format: [{"role": "user"|"assistant", "content": str}, ...]
    Ready to pass directly to the Claude messages array.
    """
    store = get_store()
    if not await store.session_exists(session_id):
        raise KeyError(f"Session '{session_id}' not found")
    return await store.get_memories(session_id, suspect_id)


async def get_prior_statements(session_id: str, suspect_id: str) -> list[str]:
    """
    Return only the assistant (character) turns as plain strings.
    Used by the consistency tool in Phase 3.
    """
    messages = await get_messages(session_id, suspect_id)
    return [m["content"] for m in messages if m["role"] == "assistant"]


async def add_evidence(session_id: str, clues: list[ExtractedClue]) -> None:
    """
    Append newly extracted clues to the session's evidence list.
    Phase 3 — called after clue extraction tool runs.
    """
    session = await get(session_id)
    session.evidence.extend(clues)
    await update(session)
