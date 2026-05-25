"""
test_chat_metadata.py — Tests for the metadata attached to the SSE done event.

The /chat route streams character tokens then closes with a done event
that carries ChatMetadata (pressure_delta, new_pressure_level, etc.).
These tests mock the orchestrator so we don't need a real Claude API key.
"""

import json
import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.services import session_service, game_service
from app.core.session_store import clear


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_store():
    clear()
    yield
    clear()


@pytest.fixture
async def live_session():
    session, scenario = await game_service.start_new_game("manor_1920")
    return session, scenario


# ── SSE parsing helper ────────────────────────────────────────────────────────

def parse_sse_events(body: str) -> list[dict]:
    """Extract parsed JSON objects from a raw SSE response body."""
    events = []
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except json.JSONDecodeError:
                pass
    return events


# ── Mock helpers ──────────────────────────────────────────────────────────────

async def _fake_stream(*args, **kwargs):
    """Async generator that yields a short fake response."""
    yield "I was"
    yield " in the kitchen."


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_done_event_is_present(live_session):
    """SSE stream must end with a 'done' event."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Where were you?",
            })

    events = parse_sse_events(response.text)
    types = [e.get("type") for e in events]
    assert "done" in types


@pytest.mark.asyncio
async def test_done_event_contains_metadata(live_session):
    """The done event must include a metadata object."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Where were you?",
            })

    events = parse_sse_events(response.text)
    done = next(e for e in events if e.get("type") == "done")
    assert "metadata" in done
    assert done["metadata"] is not None


@pytest.mark.asyncio
async def test_metadata_has_required_fields(live_session):
    """ChatMetadata must carry all expected keys."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Describe the evening.",
            })

    events = parse_sse_events(response.text)
    done = next(e for e in events if e.get("type") == "done")
    metadata = done["metadata"]

    assert "consistency_passed" in metadata
    assert "new_clues" in metadata
    assert "pressure_delta" in metadata
    assert "new_pressure_level" in metadata
    assert "new_evidence_found" in metadata


@pytest.mark.asyncio
async def test_pressure_delta_is_positive_integer(live_session):
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "What did you do at midnight?",
            })

    events = parse_sse_events(response.text)
    done = next(e for e in events if e.get("type") == "done")
    assert done["metadata"]["pressure_delta"] >= 1


@pytest.mark.asyncio
async def test_pressure_increases_after_each_turn(live_session):
    """Sending two questions should raise pressure_level to 2."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            r1 = (await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Question one.",
            })).text
            r2 = (await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Question two.",
            })).text

    e1 = next(e for e in parse_sse_events(r1) if e.get("type") == "done")
    e2 = next(e for e in parse_sse_events(r2) if e.get("type") == "done")

    level1 = e1["metadata"]["new_pressure_level"]
    level2 = e2["metadata"]["new_pressure_level"]
    assert level2 > level1


@pytest.mark.asyncio
async def test_pressure_per_suspect_is_independent(live_session):
    """Questioning the butler should not affect the niece's pressure."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Question the butler three times
            for _ in range(3):
                await client.post("/chat", json={
                    "session_id": session.session_id,
                    "suspect_id": "butler",
                    "message": "Explain yourself.",
                })
            # Ask the niece once
            niece_response = (await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "niece",
                "message": "Where were you?",
            })).text

    done = next(e for e in parse_sse_events(niece_response) if e.get("type") == "done")
    # Niece should be at pressure 1, not 4
    assert done["metadata"]["new_pressure_level"] == 1


@pytest.mark.asyncio
async def test_token_events_arrive_before_done(live_session):
    """Token events must precede the done event in the stream."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Tell me about the evening.",
            })

    events = parse_sse_events(response.text)
    types = [e.get("type") for e in events]
    assert "token" in types
    assert types.index("token") < types.index("done")


@pytest.mark.asyncio
async def test_consistency_passed_is_true(live_session):
    """consistency_passed is always True — Claude self-checks via tool loop."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Did you do it?",
            })

    events = parse_sse_events(response.text)
    done = next(e for e in events if e.get("type") == "done")
    assert done["metadata"]["consistency_passed"] is True


@pytest.mark.asyncio
async def test_session_total_questions_increments(live_session):
    """Each /chat call must increment session.total_questions."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Where were you?",
            })
            await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "niece",
                "message": "What did you see?",
            })

    updated = await session_service.get(session.session_id)
    assert updated.total_questions == 2


# ── Phase 3: dynamic pressure + clue extraction ───────────────────────────────

async def _fake_kitchen_stream(*args, **kwargs):
    """Response that contains extractable evidence: location + object + time."""
    yield "I was in the kitchen until 11 PM, tending to the decanter."


async def _fake_neutral_stream(*args, **kwargs):
    yield "I have nothing further to say on the matter."


@pytest.mark.asyncio
async def test_pressure_delta_neutral_question(live_session):
    """A neutral greeting should produce pressure_delta == 1."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_neutral_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Good evening. Could you tell me about the household?",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["pressure_delta"] == 1


@pytest.mark.asyncio
async def test_pressure_delta_pointed_question(live_session):
    """A pointed 'why' / 'explain' question should produce pressure_delta >= 2."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_neutral_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Explain exactly why no one can confirm your whereabouts.",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["pressure_delta"] >= 2


@pytest.mark.asyncio
async def test_pressure_delta_accusatory_question(live_session):
    """A direct accusation should produce pressure_delta == 3."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_neutral_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "You're lying — I have a witness who saw you.",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["pressure_delta"] == 3


@pytest.mark.asyncio
async def test_pressure_level_increments_by_delta(live_session):
    """
    After an accusatory question (delta=3) the pressure_level should
    be 3, not 1.
    """
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_neutral_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "You're lying — I have a witness who saw you.",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["new_pressure_level"] == 3


@pytest.mark.asyncio
async def test_clues_extracted_from_response(live_session):
    """Response mentioning kitchen / 11 PM / decanter should produce clues."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_kitchen_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Where were you?",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["new_clues"] != []
    assert done["metadata"]["new_evidence_found"] is True


@pytest.mark.asyncio
async def test_clue_categories_in_metadata(live_session):
    """Extracted clues must carry required fields: text, category, suspect_id, turn."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_kitchen_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Where were you?",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    for clue in done["metadata"]["new_clues"]:
        assert "text" in clue
        assert "category" in clue
        assert clue["category"] in ("time", "location", "object", "person")
        assert clue["suspect_id"] == "butler"


@pytest.mark.asyncio
async def test_neutral_response_no_clues(live_session):
    """A generic response with no entities should produce empty new_clues."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_neutral_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Do you have anything to add?",
            })

    done = next(e for e in parse_sse_events(response.text) if e.get("type") == "done")
    assert done["metadata"]["new_clues"] == []
    assert done["metadata"]["new_evidence_found"] is False


@pytest.mark.asyncio
async def test_evidence_persisted_in_session(live_session):
    """Clues from the response must be stored in session.evidence."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_kitchen_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Describe your evening.",
            })

    updated = await session_service.get(session.session_id)
    assert len(updated.evidence) > 0


@pytest.mark.asyncio
async def test_evidence_accumulates_across_turns(live_session):
    """Evidence from multiple turns should accumulate in session.evidence."""
    session, _ = live_session
    with patch("app.agents.orchestrator.stream_character_response", new=_fake_kitchen_stream):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Question one.",
            })
            await client.post("/chat", json={
                "session_id": session.session_id,
                "suspect_id": "butler",
                "message": "Question two.",
            })

    updated = await session_service.get(session.session_id)
    # Two turns of kitchen/11PM/decanter responses → at least 2 clue sets
    assert len(updated.evidence) >= 2
