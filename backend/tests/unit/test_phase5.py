"""
test_phase5.py — Tests for Phase 5: history, hint, and difficulty.

Covers:
  - GET /history returns empty list initially
  - /accuse appends a record to history
  - Multiple games accumulate in history
  - History record has correct fields
  - POST /hint returns a hint string
  - Hint returns 409 on resolved session
  - Difficulty affects score formula
  - Easy/Medium/Hard score differences
  - history_store append + get_all + clear
  - GameRecord model fields
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services import game_service
from app.core import history_store
from app.core.session_store import clear as clear_sessions
from app.models.history import GameRecord


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_all():
    """Fresh sessions and history for every test."""
    clear_sessions()
    history_store.clear()
    yield
    clear_sessions()
    history_store.clear()


@pytest.fixture
async def live_session():
    session, scenario = await game_service.start_new_game("manor_1920")
    return session, scenario


_MOCK_NARRATIVE = "The truth is revealed. Beckett did it."


def _patch_narrative():
    return patch(
        "app.services.resolution_service.generate_narrative",
        new=AsyncMock(return_value=_MOCK_NARRATIVE),
    )


# ── GET /history ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_history_empty_initially():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/history")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_history_has_record_after_accusation(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })
            history = (await client.get("/history")).json()

    assert len(history) == 1


@pytest.mark.asyncio
async def test_history_record_has_correct_fields(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })
            records = (await client.get("/history")).json()

    r = records[0]
    assert r["session_id"] == session.session_id
    assert r["is_correct"] is True
    assert r["accused_suspect_id"] == "butler"
    assert r["correct_culprit_id"] == "butler"
    assert r["player_motive"] == "embezzlement"
    assert r["player_method"] == "arsenic"
    assert "score" in r
    assert "total_questions" in r
    assert "timestamp" in r
    assert "record_id" in r


@pytest.mark.asyncio
async def test_history_two_games_accumulate():
    s1, _ = await game_service.start_new_game("manor_1920")
    s2, _ = await game_service.start_new_game("manor_1920")

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": s1.session_id,
                "suspect_id": "butler",
                "motive": "x", "method": "y",
            })
            await client.post("/accuse", json={
                "session_id": s2.session_id,
                "suspect_id": "niece",
                "motive": "a", "method": "b",
            })
            records = (await client.get("/history")).json()

    assert len(records) == 2


@pytest.mark.asyncio
async def test_history_newest_first():
    """History must be returned with the most recent game at index 0."""
    s1, _ = await game_service.start_new_game("manor_1920")
    s2, _ = await game_service.start_new_game("manor_1920")

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": s1.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })
            await client.post("/accuse", json={
                "session_id": s2.session_id,
                "suspect_id": "niece", "motive": "a", "method": "b",
            })
            records = (await client.get("/history")).json()

    # s2 was accused last — its record should be first (newest)
    assert records[0]["session_id"] == s2.session_id


# ── POST /hint ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_hint_returns_200(live_session):
    session, _ = live_session
    # Patch at the route's import site
    with patch(
        "app.api.routes.hint.generate_hint",
        new=AsyncMock(return_value="Look more closely at the timeline."),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/hint", json={"session_id": session.session_id})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_hint_returns_hint_string(live_session):
    session, _ = live_session
    with patch(
        "app.api.routes.hint.generate_hint",
        new=AsyncMock(return_value="Examine the butler's account of midnight."),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/hint", json={
                "session_id": session.session_id
            })).json()

    assert "hint" in data
    assert data["hint"] == "Examine the butler's account of midnight."


@pytest.mark.asyncio
async def test_hint_rejected_after_resolution(live_session):
    """Hints must return 409 once the game is resolved."""
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })
            hint_response = await client.post("/hint", json={
                "session_id": session.session_id
            })

    assert hint_response.status_code == 409


@pytest.mark.asyncio
async def test_hint_missing_session_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/hint", json={"session_id": "ghost-session"})
    assert response.status_code == 404


# ── Difficulty scoring ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_easy_mode_lower_score_penalty():
    """Easy mode penalises fewer points per question than medium."""
    s_easy,   _ = await game_service.start_new_game("manor_1920", difficulty="easy")
    s_medium, _ = await game_service.start_new_game("manor_1920", difficulty="medium")

    # Simulate 10 questions each
    s_easy.total_questions   = 10
    s_medium.total_questions = 10
    from app.services import session_service
    await session_service.update(s_easy)
    await session_service.update(s_medium)

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            easy_score   = (await client.post("/accuse", json={
                "session_id": s_easy.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })).json()["score"]
            medium_score = (await client.post("/accuse", json={
                "session_id": s_medium.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })).json()["score"]

    assert easy_score > medium_score


@pytest.mark.asyncio
async def test_hard_mode_higher_score_penalty():
    """Hard mode penalises more points per question than medium."""
    s_medium, _ = await game_service.start_new_game("manor_1920", difficulty="medium")
    s_hard,   _ = await game_service.start_new_game("manor_1920", difficulty="hard")

    s_medium.total_questions = 10
    s_hard.total_questions   = 10
    from app.services import session_service
    await session_service.update(s_medium)
    await session_service.update(s_hard)

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            medium_score = (await client.post("/accuse", json={
                "session_id": s_medium.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })).json()["score"]
            hard_score   = (await client.post("/accuse", json={
                "session_id": s_hard.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })).json()["score"]

    assert hard_score < medium_score


@pytest.mark.asyncio
async def test_difficulty_stored_in_history_record():
    s_hard, _ = await game_service.start_new_game("manor_1920", difficulty="hard")
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": s_hard.session_id,
                "suspect_id": "butler", "motive": "x", "method": "y",
            })
            records = (await client.get("/history")).json()

    assert records[0]["difficulty"] == "hard"


# ── history_store unit tests ──────────────────────────────────────────────────

def test_history_store_empty_initially():
    assert history_store.get_all() == []


def test_history_store_append_and_get():
    record = GameRecord(
        session_id="sess-1",
        scenario_id="manor_1920",
        is_correct=True,
        score=80,
        total_questions=10,
        accused_suspect_id="butler",
        player_motive="greed",
        player_method="arsenic",
        correct_culprit_id="butler",
    )
    history_store.append(record)
    all_records = history_store.get_all()
    assert len(all_records) == 1
    assert all_records[0].session_id == "sess-1"
    assert all_records[0].is_correct is True


def test_history_store_newest_first():
    for i in range(3):
        history_store.append(GameRecord(
            session_id=f"sess-{i}",
            scenario_id="manor_1920",
            is_correct=True,
            score=80 - i * 10,
            total_questions=i,
            accused_suspect_id="butler",
            player_motive="x",
            player_method="y",
            correct_culprit_id="butler",
        ))
    all_records = history_store.get_all()
    assert all_records[0].session_id == "sess-2"   # last appended is first


def test_history_store_clear():
    history_store.append(GameRecord(
        session_id="sess-x",
        scenario_id="manor_1920",
        is_correct=False,
        score=0,
        total_questions=5,
        accused_suspect_id="niece",
        player_motive="x",
        player_method="y",
        correct_culprit_id="butler",
    ))
    history_store.clear()
    assert history_store.get_all() == []
