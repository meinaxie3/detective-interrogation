"""
test_redis_store.py — Integration tests for the Redis-backed session store.

These tests require a running Redis instance. They are SKIPPED by default.
To run them:
  1. Start Redis:  docker run -p 6379:6379 redis:7-alpine
  2. Run with:     REDIS_URL=redis://localhost:6379/15 pytest tests/integration/

The tests use DB 15 (TEST_REDIS_DB) so they never touch real data.
"""

import os
import json
import pytest

REDIS_URL = os.getenv("REDIS_URL")
pytestmark = pytest.mark.skipif(
    not REDIS_URL,
    reason="REDIS_URL not set — skipping Redis integration tests",
)


@pytest.fixture
async def redis_store():
    """Fresh RedisStore pointing at the test DB; flushed before and after."""
    from app.core.session_store import RedisStore
    store = RedisStore(REDIS_URL, ttl=60)  # short TTL for tests
    await store.clear()
    yield store
    await store.clear()
    await store.close()


# ── session_exists ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_session_exists_false_for_new_id(redis_store):
    assert await redis_store.session_exists("ghost-session") is False


@pytest.mark.asyncio
async def test_session_exists_true_after_set(redis_store):
    await redis_store.set_session_data("s1", {"scenario_id": "manor_1920"})
    assert await redis_store.session_exists("s1") is True


# ── get / set session data ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_set_then_get_session_data(redis_store):
    data = {"scenario_id": "manor_1920", "total_questions": 0}
    await redis_store.set_session_data("s1", data)
    result = await redis_store.get_session_data("s1")
    assert result == data


@pytest.mark.asyncio
async def test_get_missing_session_returns_none(redis_store):
    result = await redis_store.get_session_data("does-not-exist")
    assert result is None


@pytest.mark.asyncio
async def test_overwrite_session_data(redis_store):
    await redis_store.set_session_data("s1", {"total_questions": 0})
    await redis_store.set_session_data("s1", {"total_questions": 5})
    result = await redis_store.get_session_data("s1")
    assert result["total_questions"] == 5


@pytest.mark.asyncio
async def test_sessions_are_isolated(redis_store):
    await redis_store.set_session_data("s1", {"x": 1})
    await redis_store.set_session_data("s2", {"x": 99})
    r1 = await redis_store.get_session_data("s1")
    assert r1["x"] == 1


# ── conversation memories ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_memories_empty_for_new_suspect(redis_store):
    await redis_store.set_session_data("s1", {})
    msgs = await redis_store.get_memories("s1", "butler")
    assert msgs == []


@pytest.mark.asyncio
async def test_append_then_get_memories(redis_store):
    await redis_store.set_session_data("s1", {})
    await redis_store.append_memory("s1", "butler", {"role": "user", "content": "Q1"})
    await redis_store.append_memory("s1", "butler", {"role": "assistant", "content": "A1"})

    msgs = await redis_store.get_memories("s1", "butler")
    assert len(msgs) == 2
    assert msgs[0] == {"role": "user", "content": "Q1"}
    assert msgs[1] == {"role": "assistant", "content": "A1"}


@pytest.mark.asyncio
async def test_memories_isolated_per_suspect(redis_store):
    await redis_store.set_session_data("s1", {})
    await redis_store.append_memory("s1", "butler", {"role": "user", "content": "butler Q"})
    await redis_store.append_memory("s1", "niece", {"role": "user", "content": "niece Q"})

    butler = await redis_store.get_memories("s1", "butler")
    niece = await redis_store.get_memories("s1", "niece")
    assert len(butler) == 1
    assert len(niece) == 1
    assert butler[0]["content"] == "butler Q"
    assert niece[0]["content"] == "niece Q"


@pytest.mark.asyncio
async def test_memories_isolated_per_session(redis_store):
    await redis_store.set_session_data("s1", {})
    await redis_store.set_session_data("s2", {})
    await redis_store.append_memory("s1", "butler", {"role": "user", "content": "session 1"})

    s2_msgs = await redis_store.get_memories("s2", "butler")
    assert s2_msgs == []


@pytest.mark.asyncio
async def test_memory_order_preserved(redis_store):
    await redis_store.set_session_data("s1", {})
    for i in range(5):
        await redis_store.append_memory("s1", "butler", {"role": "user", "content": f"Q{i}"})

    msgs = await redis_store.get_memories("s1", "butler")
    contents = [m["content"] for m in msgs]
    assert contents == ["Q0", "Q1", "Q2", "Q3", "Q4"]


# ── clear ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_clear_removes_all_sessions(redis_store):
    await redis_store.set_session_data("s1", {})
    await redis_store.set_session_data("s2", {})
    await redis_store.clear()
    assert await redis_store.get_session_data("s1") is None
    assert await redis_store.get_session_data("s2") is None
