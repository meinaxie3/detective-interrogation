"""
test_game_flow.py — Integration tests for the full game lifecycle.

Tests the sequence: new game → interrogate suspects → accuse → resolution.
These require a running FastAPI app + Redis (use pytest-asyncio + httpx).
Skipped in CI unless INTEGRATION=true is set.

To run locally:
  INTEGRATION=true pytest tests/integration/

Claude API calls are mocked — we don't want real LLM calls in tests.
Redis is a real local instance (or testcontainers in CI).
"""

import pytest
import os
from httpx import AsyncClient

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "true",
    reason="Integration tests require INTEGRATION=true and a running Redis"
)


@pytest.fixture
async def client():
    """Async test client for the FastAPI app."""
    # TODO (Phase 2): import app and wrap in AsyncClient
    # from app.main import app
    # async with AsyncClient(app=app, base_url="http://test") as ac:
    #     yield ac
    pytest.skip("Requires Phase 1 app implementation")


@pytest.fixture
def mock_claude(monkeypatch):
    """
    Patch the Anthropic client so all Claude calls return a fixed response.
    This keeps integration tests fast and deterministic.
    """
    # TODO (Phase 1): patch anthropic.Anthropic or AsyncAnthropic
    pass


# ── Game lifecycle ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_new_game_creates_session(client, mock_claude):
    """POST /new-game should return a session_id and a list of suspect summaries."""
    response = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    assert response.status_code == 200
    body = response.json()
    assert "session_id" in body
    assert len(body["suspects"]) == 3
    assert all("id" in s and "name" in s for s in body["suspects"])


@pytest.mark.asyncio
async def test_new_game_does_not_expose_hidden_fields(client, mock_claude):
    """
    The suspects returned by /new-game must not include is_culprit,
    alibi_hole, actual_location, or what_they_hide.
    """
    response = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    suspects = response.json()["suspects"]
    for suspect in suspects:
        assert "is_culprit" not in suspect
        assert "alibi_hole" not in suspect
        assert "actual_location" not in suspect
        assert "what_they_hide" not in suspect


@pytest.mark.asyncio
async def test_chat_returns_streamed_response(client, mock_claude):
    """POST /chat should return a streaming SSE response."""
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    response = await client.post("/chat", json={
        "session_id": session_id,
        "suspect_id": "butler",
        "message": "Good evening. Where were you last night?"
    })
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_chat_increments_question_count(client, mock_claude):
    """Each message to /chat should increment the session's total_questions counter."""
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    await client.post("/chat", json={
        "session_id": session_id, "suspect_id": "butler",
        "message": "Where were you last night?"
    })

    session = await client.get(f"/session/{session_id}")
    assert session.json()["session"]["total_questions"] == 1


@pytest.mark.asyncio
async def test_switching_suspects_uses_separate_memory(client, mock_claude):
    """
    Talking to suspect A and then suspect B should NOT mix their
    conversation histories. Each suspect has an isolated memory.
    """
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    await client.post("/chat", json={
        "session_id": session_id, "suspect_id": "butler",
        "message": "Tell me about yourself."
    })
    await client.post("/chat", json={
        "session_id": session_id, "suspect_id": "niece",
        "message": "Tell me about yourself."
    })

    # Each suspect should have exactly 1 message in their history
    session_data = (await client.get(f"/session/{session_id}")).json()
    butler_state = session_data["session"]["suspect_states"].get("butler", {})
    niece_state  = session_data["session"]["suspect_states"].get("niece", {})
    assert butler_state.get("message_count", 0) == 1
    assert niece_state.get("message_count", 0) == 1


# ── Accusation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_correct_accusation_returns_win(client, mock_claude):
    """Accusing the actual culprit with the real motive should return is_correct=True."""
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    response = await client.post("/accuse", json={
        "session_id": session_id,
        "suspect_id": "butler",
        "motive": "embezzlement cover-up",
        "method": "arsenic in the wine",
    })
    assert response.status_code == 200
    assert response.json()["is_correct"] is True
    assert "resolution_narrative" in response.json()


@pytest.mark.asyncio
async def test_incorrect_accusation_returns_loss(client, mock_claude):
    """Accusing the wrong suspect should return is_correct=False."""
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    response = await client.post("/accuse", json={
        "session_id": session_id,
        "suspect_id": "niece",       # wrong suspect
        "motive": "inheritance",
        "method": "arsenic in the wine",
    })
    assert response.json()["is_correct"] is False
    assert response.json()["correct_culprit_id"] == "butler"


@pytest.mark.asyncio
async def test_cannot_chat_after_accusation(client, mock_claude):
    """Once an accusation is made, the game phase is RESOLVED and chat is locked."""
    new_game = await client.post("/new-game", json={"scenario_id": "manor_1920"})
    session_id = new_game.json()["session_id"]

    await client.post("/accuse", json={
        "session_id": session_id, "suspect_id": "butler",
        "motive": "embezzlement", "method": "arsenic"
    })

    chat_response = await client.post("/chat", json={
        "session_id": session_id, "suspect_id": "butler",
        "message": "One more question..."
    })
    assert chat_response.status_code == 409   # Conflict — game already resolved


@pytest.mark.asyncio
async def test_invalid_session_id_returns_404(client, mock_claude):
    """All endpoints should return 404 for a session that doesn't exist."""
    response = await client.post("/chat", json={
        "session_id": "nonexistent-id",
        "suspect_id": "butler",
        "message": "Hello?"
    })
    assert response.status_code == 404
