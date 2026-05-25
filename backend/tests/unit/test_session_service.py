"""
test_session_service.py — Unit tests for session_service.

Tests the in-memory backing store. The same tests will run against
the Redis implementation in Phase 2 without modification — that's
the point of keeping the interface identical.

Each test gets a clean store via the autouse fixture.
"""

import pytest
from app.models.session import GameSessionModel, SuspectInteractionState, GamePhase
from app.services import session_service
from app.core.session_store import clear


@pytest.fixture(autouse=True)
def reset_store():
    """Ensure every test starts with an empty in-memory store."""
    clear()
    yield
    clear()


# ── create / get / update ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_then_get_returns_same_session():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    retrieved = await session_service.get(session.session_id)
    assert retrieved.session_id == session.session_id
    assert retrieved.scenario_id == "manor_1920"


@pytest.mark.asyncio
async def test_get_raises_key_error_for_missing_session():
    with pytest.raises(KeyError, match="not found"):
        await session_service.get("this-does-not-exist")


@pytest.mark.asyncio
async def test_update_persists_phase_change():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    session.phase = GamePhase.RESOLVED
    await session_service.update(session)

    retrieved = await session_service.get(session.session_id)
    assert retrieved.phase == GamePhase.RESOLVED


@pytest.mark.asyncio
async def test_update_persists_question_count():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    session.total_questions = 7
    await session_service.update(session)

    retrieved = await session_service.get(session.session_id)
    assert retrieved.total_questions == 7


@pytest.mark.asyncio
async def test_update_raises_for_missing_session():
    session = GameSessionModel(scenario_id="manor_1920")
    # Never created — should raise
    with pytest.raises(KeyError):
        await session_service.update(session)


@pytest.mark.asyncio
async def test_multiple_sessions_are_isolated():
    s1 = GameSessionModel(scenario_id="manor_1920")
    s2 = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(s1)
    await session_service.create(s2)

    s1.total_questions = 3
    await session_service.update(s1)

    r2 = await session_service.get(s2.session_id)
    assert r2.total_questions == 0   # s2 untouched


# ── append_message / get_messages ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_append_and_get_messages_basic():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    await session_service.append_message(session.session_id, "butler", "user", "Where were you?")
    await session_service.append_message(session.session_id, "butler", "assistant", "In the kitchen.")

    messages = await session_service.get_messages(session.session_id, "butler")
    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Where were you?"}
    assert messages[1] == {"role": "assistant", "content": "In the kitchen."}


@pytest.mark.asyncio
async def test_get_messages_returns_empty_for_unquestioned_suspect():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    messages = await session_service.get_messages(session.session_id, "butler")
    assert messages == []


@pytest.mark.asyncio
async def test_messages_are_isolated_per_suspect():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    await session_service.append_message(session.session_id, "butler", "user", "Butler question")
    await session_service.append_message(session.session_id, "niece",  "user", "Niece question")

    butler_msgs = await session_service.get_messages(session.session_id, "butler")
    niece_msgs  = await session_service.get_messages(session.session_id, "niece")

    assert len(butler_msgs) == 1
    assert len(niece_msgs)  == 1
    assert butler_msgs[0]["content"] == "Butler question"
    assert niece_msgs[0]["content"]  == "Niece question"


@pytest.mark.asyncio
async def test_messages_accumulate_in_order():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    for i in range(5):
        await session_service.append_message(session.session_id, "butler", "user", f"Q{i}")
        await session_service.append_message(session.session_id, "butler", "assistant", f"A{i}")

    messages = await session_service.get_messages(session.session_id, "butler")
    assert len(messages) == 10
    assert messages[0]["content"] == "Q0"
    assert messages[-1]["content"] == "A4"


@pytest.mark.asyncio
async def test_append_message_rejects_invalid_role():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    with pytest.raises(ValueError, match="role"):
        await session_service.append_message(session.session_id, "butler", "detective", "hello")


# ── get_prior_statements ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_prior_statements_returns_only_assistant_turns():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    await session_service.append_message(session.session_id, "butler", "user", "Player question")
    await session_service.append_message(session.session_id, "butler", "assistant", "Character response")
    await session_service.append_message(session.session_id, "butler", "user", "Follow-up")

    priors = await session_service.get_prior_statements(session.session_id, "butler")
    assert priors == ["Character response"]


@pytest.mark.asyncio
async def test_get_prior_statements_empty_for_new_suspect():
    session = GameSessionModel(scenario_id="manor_1920")
    await session_service.create(session)

    priors = await session_service.get_prior_statements(session.session_id, "butler")
    assert priors == []
