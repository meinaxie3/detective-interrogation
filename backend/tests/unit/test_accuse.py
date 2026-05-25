"""
test_accuse.py — Integration-style unit tests for POST /accuse.

Uses httpx AsyncClient against the real FastAPI app with a fresh
in-memory session for each test.

Phase 2: pure game-logic tests (correct/wrong accusation, score, session state).
Phase 4: resolution narrative tests (mock Claude call, fallback, content quality).

All tests mock the resolution service so no live Claude API call is needed.
The mock returns the fallback narrative, which is always non-empty and
contains the culprit's name (Beckett).
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services import session_service, game_service
from app.core.session_store import clear


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_store():
    """Fresh in-memory store for every test."""
    clear()
    yield
    clear()


@pytest.fixture
async def live_session():
    """Start a real game session and return (session, scenario)."""
    session, scenario = await game_service.start_new_game("manor_1920")
    return session, scenario


# ── Shared mock narrative ─────────────────────────────────────────────────────

_MOCK_NARRATIVE = (
    "Your instincts were correct, Detective. Beckett is guilty. "
    "The investigation is now closed."
)

_WRONG_NARRATIVE = (
    "An understandable conclusion, but the wrong one. "
    "The true culprit was Beckett. The investigation is now closed."
)


def _patch_narrative(narrative: str = _MOCK_NARRATIVE):
    """Context manager that patches resolution_service.generate_narrative."""
    return patch(
        "app.services.resolution_service.generate_narrative",
        new=AsyncMock(return_value=narrative),
    )


# ── Happy-path tests ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_correct_accusation_returns_200(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement cover-up",
                "method": "arsenic in the wine",
            })
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_correct_accusation_is_correct_true(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()
    assert data["is_correct"] is True


@pytest.mark.asyncio
async def test_correct_accusation_correct_culprit_id(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()
    assert data["correct_culprit_id"] == "butler"


@pytest.mark.asyncio
async def test_correct_accusation_returns_non_zero_score(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()
    assert data["score"] > 0


@pytest.mark.asyncio
async def test_correct_accusation_returns_narrative(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()
    assert len(data["resolution_narrative"]) > 50
    assert "Beckett" in data["resolution_narrative"]  # culprit name in narrative


# ── Wrong-suspect tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_wrong_suspect_is_correct_false(live_session):
    session, _ = live_session
    with _patch_narrative(_WRONG_NARRATIVE):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "niece",
                "motive": "inheritance",
                "method": "poison",
            })).json()
    assert data["is_correct"] is False


@pytest.mark.asyncio
async def test_wrong_suspect_reveals_real_culprit(live_session):
    session, _ = live_session
    with _patch_narrative(_WRONG_NARRATIVE):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "niece",
                "motive": "inheritance",
                "method": "poison",
            })).json()
    assert data["correct_culprit_id"] == "butler"
    assert "butler" in data["correct_culprit_id"]


@pytest.mark.asyncio
async def test_wrong_suspect_lower_score_than_correct(live_session):
    """Wrong guess should score lower than a correct guess (all else equal)."""
    session_right, _ = await game_service.start_new_game("manor_1920")
    session_wrong, _ = await game_service.start_new_game("manor_1920")

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            right = (await client.post("/accuse", json={
                "session_id": session_right.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()
            wrong = (await client.post("/accuse", json={
                "session_id": session_wrong.session_id,
                "suspect_id": "niece",
                "motive": "inheritance",
                "method": "poison",
            })).json()

    assert right["score"] > wrong["score"]


# ── Session state tests ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accuse_sets_session_phase_to_resolved(live_session):
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
    updated = await session_service.get(session.session_id)
    assert updated.phase.value == "resolved"


@pytest.mark.asyncio
async def test_accuse_records_is_correct_on_session(live_session):
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
    updated = await session_service.get(session.session_id)
    assert updated.is_correct is True


@pytest.mark.asyncio
async def test_accuse_stores_accusation_on_session(live_session):
    session, _ = live_session
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "greed",
                "method": "arsenic",
            })
    updated = await session_service.get(session.session_id)
    assert updated.accusation is not None
    assert updated.accusation.suspect_id == "butler"
    assert updated.accusation.motive == "greed"


# ── Error / edge-case tests ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accuse_missing_session_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/accuse", json={
            "session_id": "nonexistent-abc-123",
            "suspect_id": "butler",
            "motive": "x",
            "method": "y",
        })
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_double_accuse_returns_409(live_session):
    """Second accusation on a resolved session must be rejected."""
    session, _ = live_session
    payload = {
        "session_id": session.session_id,
        "suspect_id": "butler",
        "motive": "embezzlement",
        "method": "arsenic",
    }
    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json=payload)           # first
            response = await client.post("/accuse", json=payload)   # second
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_score_decreases_with_more_questions(live_session):
    """More questions asked -> lower score."""
    session, _ = live_session

    session.total_questions = 20
    await session_service.update(session)

    with _patch_narrative():
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()

    assert data["score"] < 100


# ── Phase 4: resolution narrative tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_resolution_service_is_called_once(live_session):
    """The resolution service must be called exactly once per accusation."""
    session, _ = live_session
    mock_gen = AsyncMock(return_value=_MOCK_NARRATIVE)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })

    mock_gen.assert_called_once()


@pytest.mark.asyncio
async def test_resolution_service_receives_is_correct_true(live_session):
    """Correct accusation must pass is_correct=True to the service."""
    session, _ = live_session
    mock_gen = AsyncMock(return_value=_MOCK_NARRATIVE)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })

    _, kwargs = mock_gen.call_args
    assert kwargs["is_correct"] is True


@pytest.mark.asyncio
async def test_resolution_service_receives_is_correct_false(live_session):
    """Wrong accusation must pass is_correct=False to the service."""
    session, _ = live_session
    mock_gen = AsyncMock(return_value=_WRONG_NARRATIVE)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "niece",
                "motive": "inheritance",
                "method": "poison",
            })

    _, kwargs = mock_gen.call_args
    assert kwargs["is_correct"] is False


@pytest.mark.asyncio
async def test_resolution_service_receives_player_motive(live_session):
    """The player's stated motive must be forwarded to the service."""
    session, _ = live_session
    mock_gen = AsyncMock(return_value=_MOCK_NARRATIVE)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement cover-up",
                "method": "arsenic",
            })

    _, kwargs = mock_gen.call_args
    assert kwargs["player_motive"] == "embezzlement cover-up"


@pytest.mark.asyncio
async def test_resolution_service_receives_player_method(live_session):
    """The player's stated method must be forwarded to the service."""
    session, _ = live_session
    mock_gen = AsyncMock(return_value=_MOCK_NARRATIVE)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic in the evening wine",
            })

    _, kwargs = mock_gen.call_args
    assert kwargs["player_method"] == "arsenic in the evening wine"


@pytest.mark.asyncio
async def test_narrative_from_service_returned_verbatim(live_session):
    """Whatever the service returns must appear unchanged in the response."""
    session, _ = live_session
    custom_narrative = "A most singular affair. Beckett could not escape the truth."
    mock_gen = AsyncMock(return_value=custom_narrative)

    with patch("app.services.resolution_service.generate_narrative", new=mock_gen):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()

    assert data["resolution_narrative"] == custom_narrative


@pytest.mark.asyncio
async def test_fallback_narrative_used_in_mock_mode(live_session):
    """
    When USE_MOCK=true, the fallback template is used — no Claude call.
    The fallback always includes the culprit's name (Beckett).
    """
    session, _ = live_session

    # Patch settings.use_mock=True so the service uses the fallback path
    with patch("app.services.resolution_service.settings") as mock_settings:
        mock_settings.use_mock = True
        mock_settings.anthropic_api_key = ""
        mock_settings.claude_model = "claude-sonnet-4-5"

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            data = (await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })).json()

    assert len(data["resolution_narrative"]) > 50
    assert "Beckett" in data["resolution_narrative"]


@pytest.mark.asyncio
async def test_fallback_narrative_used_when_claude_fails(live_session):
    """If Claude raises an exception, the fallback is returned (no crash)."""
    session, _ = live_session

    async def _broken_generate(**kwargs):
        raise RuntimeError("Claude API unavailable")

    # Patch at the service function level to simulate an internal error
    with patch(
        "app.services.resolution_service.anthropic.AsyncAnthropic",
        side_effect=RuntimeError("Claude API unavailable"),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Ensure the route still returns 200 (not 500)
            response = await client.post("/accuse", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "motive": "embezzlement",
                "method": "arsenic",
            })

    assert response.status_code == 200
    data = response.json()
    assert "Beckett" in data["resolution_narrative"]


@pytest.mark.asyncio
async def test_resolution_prompt_correct_accusation():
    """build() prompt for a correct accusation mentions the culprit and true motive."""
    from app.prompts.resolution import build
    from app.services.scenario_service import load

    scenario = load("manor_1920")
    culprit = next(s for s in scenario.suspects if s.is_culprit)

    prompt = build(
        scenario=scenario,
        player_suspect=culprit,
        player_motive="embezzlement cover-up",
        player_method="arsenic in the wine",
        is_correct=True,
    )

    assert culprit.name in prompt
    assert scenario.true_motive in prompt
    assert "correctly identified" in prompt


@pytest.mark.asyncio
async def test_resolution_prompt_wrong_accusation():
    """build() prompt for a wrong accusation mentions correction language."""
    from app.prompts.resolution import build
    from app.services.scenario_service import load

    scenario = load("manor_1920")
    culprit = next(s for s in scenario.suspects if s.is_culprit)
    wrong_suspect = next(s for s in scenario.suspects if not s.is_culprit)

    prompt = build(
        scenario=scenario,
        player_suspect=wrong_suspect,
        player_motive="inheritance",
        player_method="poison",
        is_correct=False,
    )

    assert wrong_suspect.name in prompt
    assert culprit.name in prompt
    assert "incorrect" in prompt or "wrong" in prompt or "correct their mistake" in prompt


@pytest.mark.asyncio
async def test_fallback_correct_accusation_contains_culprit():
    """Fallback narrative for correct accusation always contains the culprit name."""
    from app.services.resolution_service import _fallback
    from app.services.scenario_service import load

    scenario = load("manor_1920")
    culprit = next(s for s in scenario.suspects if s.is_culprit)

    narrative = _fallback(scenario, culprit, is_correct=True)
    assert culprit.name in narrative
    assert len(narrative) > 50


@pytest.mark.asyncio
async def test_fallback_wrong_accusation_reveals_real_culprit():
    """Fallback narrative for wrong accusation names the real culprit."""
    from app.services.resolution_service import _fallback
    from app.services.scenario_service import load

    scenario = load("manor_1920")
    culprit = next(s for s in scenario.suspects if s.is_culprit)
    wrong_suspect = next(s for s in scenario.suspects if not s.is_culprit)

    narrative = _fallback(scenario, wrong_suspect, is_correct=False)
    assert culprit.name in narrative
    assert wrong_suspect.name in narrative
