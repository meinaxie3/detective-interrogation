"""
test_models.py — Unit tests for Pydantic model behaviour.

Verifies that the data models enforce their contracts correctly:
  - Required fields are enforced
  - Serialisation round-trips correctly (important for Redis storage)
  - Default values are sensible
  - Enums behave as expected

No I/O, no Claude API, no Redis — pure model logic only.
"""

import pytest
from pydantic import ValidationError
from app.models.session import (
    GameSessionModel, GamePhase, ExtractedClue,
    SuspectInteractionState, AccusationModel
)
from app.models.chat import ChatRequest, AccuseRequest, AccuseResponse
from app.models.game import NewGameResponse, SuspectSummary


# ── GameSessionModel ──────────────────────────────────────────────────────────

def test_session_starts_in_investigation_phase():
    session = GameSessionModel(scenario_id="manor_1920")
    assert session.phase == GamePhase.INVESTIGATION


def test_session_starts_with_empty_evidence():
    session = GameSessionModel(scenario_id="manor_1920")
    assert session.evidence == []


def test_session_starts_with_no_accusation():
    session = GameSessionModel(scenario_id="manor_1920")
    assert session.accusation is None
    assert session.is_correct is None


def test_session_id_is_auto_generated():
    s1 = GameSessionModel(scenario_id="manor_1920")
    s2 = GameSessionModel(scenario_id="manor_1920")
    assert s1.session_id != s2.session_id


def test_session_serialises_to_dict():
    """Session must round-trip through dict for Redis JSON storage."""
    session = GameSessionModel(scenario_id="manor_1920")
    data = session.model_dump()
    restored = GameSessionModel(**data)
    assert restored.session_id == session.session_id
    assert restored.phase == session.phase


def test_session_serialises_to_json_string():
    """JSON serialisation must not lose any fields."""
    session = GameSessionModel(scenario_id="manor_1920")
    json_str = session.model_dump_json()
    restored = GameSessionModel.model_validate_json(json_str)
    assert restored.scenario_id == session.scenario_id


# ── SuspectInteractionState ───────────────────────────────────────────────────

def test_suspect_state_starts_at_zero_pressure():
    state = SuspectInteractionState(suspect_id="butler")
    assert state.pressure_level == 0
    assert state.questions_asked == 0
    assert state.has_been_questioned is False


def test_suspect_state_requires_suspect_id():
    with pytest.raises(ValidationError):
        SuspectInteractionState()  # type: ignore


# ── ExtractedClue ─────────────────────────────────────────────────────────────

def test_extracted_clue_gets_auto_id():
    c1 = ExtractedClue(suspect_id="butler", text="kitchen", category="location", turn=1)
    c2 = ExtractedClue(suspect_id="butler", text="kitchen", category="location", turn=1)
    assert c1.clue_id != c2.clue_id


def test_extracted_clue_requires_category():
    with pytest.raises(ValidationError):
        ExtractedClue(suspect_id="butler", text="kitchen", turn=1)  # missing category


# ── ChatRequest ───────────────────────────────────────────────────────────────

def test_chat_request_requires_all_fields():
    with pytest.raises(ValidationError):
        ChatRequest(session_id="abc")  # missing suspect_id and message


def test_chat_request_accepts_valid_payload():
    req = ChatRequest(session_id="abc123", suspect_id="butler", message="Where were you?")
    assert req.message == "Where were you?"


# ── AccuseRequest / AccuseResponse ────────────────────────────────────────────

def test_accuse_request_requires_all_fields():
    with pytest.raises(ValidationError):
        AccuseRequest(session_id="abc")  # type: ignore


def test_accuse_response_contains_resolution_narrative():
    resp = AccuseResponse(
        is_correct=True,
        correct_culprit_id="butler",
        correct_motive="embezzlement cover-up",
        correct_method="arsenic in the wine",
        score=12,
        resolution_narrative="The butler did it.",
    )
    assert resp.resolution_narrative


# ── SuspectSummary (public-facing) ────────────────────────────────────────────

def test_suspect_summary_has_no_hidden_fields():
    """
    SuspectSummary is sent to the frontend and must NOT expose
    alibi_hole, what_they_hide, actual_location, or is_culprit.
    """
    summary = SuspectSummary(
        id="butler",
        name="James Beckett",
        cover_story="Was in the kitchen all evening",
    )
    summary_dict = summary.model_dump()
    forbidden_fields = {"alibi_hole", "what_they_hide", "actual_location", "is_culprit"}
    assert not forbidden_fields.intersection(summary_dict.keys()), (
        "SuspectSummary must not expose hidden fields to the frontend"
    )
