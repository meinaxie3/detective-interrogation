"""
test_orchestrator.py — Unit tests for the Phase 3 orchestrator tool loop.

Strategy: mock the Anthropic AsyncAnthropic client so no real API calls
are made.  We simulate Claude returning tool_use and then end_turn responses
to verify the loop dispatches tools correctly and yields the final text.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.orchestrator import stream_character_response, _dispatch_tool
from app.models.scenario import ScenarioModel, SuspectModel, CrimeModel
from app.models.session import GameSessionModel, SuspectInteractionState


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def scenario():
    return ScenarioModel(
        scenario_id="test",
        title="Test Case",
        setting="A Victorian manor.",
        crime=CrimeModel(
            victim="Lord Test",
            method="poison",
            time_of_death="11:45 PM",
            location="study",
        ),
        culprit_id="butler",
        true_motive="greed",
        suspects=[
            SuspectModel(
                id="butler",
                name="James Beckett",
                cover_story="I was in the kitchen.",
                actual_location="study",
                alibi_hole="No witness after 11:30 PM",
                what_they_know=["The decanter was poisoned."],
                what_they_hide=["I entered the study at 11:40 PM."],
                emotional_tells="Grips the chair arms when nervous.",
                pressure_threshold=8,
                is_culprit=True,
            ),
            SuspectModel(
                id="niece",
                name="Clara Ashworth",
                cover_story="I was in my room reading.",
                actual_location="hallway",
                alibi_hole="She was out that night.",
                what_they_know=["She saw a figure in the hallway."],
                what_they_hide=["She was visiting someone."],
                emotional_tells="Fidgets with her ring when lying.",
                pressure_threshold=5,
                is_culprit=False,
            ),
        ],
    )


@pytest.fixture
def session(scenario):
    s = GameSessionModel(scenario_id=scenario.scenario_id)
    for suspect in scenario.suspects:
        s.suspect_states[suspect.id] = SuspectInteractionState(suspect_id=suspect.id)
    return s


@pytest.fixture
def butler(scenario):
    return next(s for s in scenario.suspects if s.id == "butler")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_text_response(text: str) -> MagicMock:
    """Simulate a Claude response with a plain text block (stop_reason=end_turn)."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [block]
    return resp


def _make_tool_response(tool_name: str, tool_id: str, tool_input: dict) -> MagicMock:
    """Simulate a Claude response that calls one tool (stop_reason=tool_use)."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = tool_name
    block.input = tool_input
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


async def _collect(gen) -> str:
    """Exhaust an async generator and join all yielded strings."""
    tokens = []
    async for tok in gen:
        tokens.append(tok)
    return "".join(tokens)


# ── Mock mode ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mock_mode_bypasses_claude(scenario, butler, session):
    """USE_MOCK=true should yield scripted tokens without touching the SDK."""
    with patch("app.agents.orchestrator.settings") as mock_settings:
        mock_settings.use_mock = True

        result = await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Where were you?",
                conversation_history=[],
            )
        )

    assert len(result) > 0
    # The scripted butler response starts with "I spent the entire evening"
    assert "kitchen" in result.lower() or len(result) > 5


# ── Tool loop ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_direct_text_response_no_tools(scenario, butler, session):
    """If Claude responds with text directly (no tools), tokens are yielded."""
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_text_response("I was in the kitchen, Detective.")
    )

    with patch("app.agents.orchestrator._get_client", return_value=mock_client), \
         patch("app.agents.orchestrator.settings") as s:
        s.use_mock = False
        s.anthropic_api_key = "sk-test"
        s.claude_model = "claude-3-haiku-20240307"
        s.max_response_tokens = 512

        result = await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Where were you?",
                conversation_history=[],
            )
        )

    assert result == "I was in the kitchen, Detective."
    assert mock_client.messages.create.call_count == 1


@pytest.mark.asyncio
async def test_tool_call_then_text_response(scenario, butler, session):
    """
    Claude calls check_consistency first, then gives a text response.
    Orchestrator should make two API calls total.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=[
        _make_tool_response(
            "check_consistency",
            "tool_abc",
            {
                "draft_response": "I was in the kitchen.",
                "prior_statements": [],
                "suspect_id": "butler",
            },
        ),
        _make_text_response("I was in the kitchen, sir."),
    ])

    with patch("app.agents.orchestrator._get_client", return_value=mock_client), \
         patch("app.agents.orchestrator.settings") as s:
        s.use_mock = False
        s.anthropic_api_key = "sk-test"
        s.claude_model = "claude-3-haiku-20240307"
        s.max_response_tokens = 512

        result = await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Where were you?",
                conversation_history=[],
            )
        )

    assert result == "I was in the kitchen, sir."
    assert mock_client.messages.create.call_count == 2


@pytest.mark.asyncio
async def test_two_tool_calls_then_text(scenario, butler, session):
    """
    Claude calls get_pressure_level, then check_consistency, then responds.
    Orchestrator should make three API calls.
    """
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(side_effect=[
        _make_tool_response(
            "get_pressure_level",
            "tool_p1",
            {"player_message": "Why?", "conversation_history": [], "current_pressure": 0},
        ),
        _make_tool_response(
            "check_consistency",
            "tool_c1",
            {"draft_response": "I was in the kitchen.", "prior_statements": [], "suspect_id": "butler"},
        ),
        _make_text_response("I was in the kitchen, Detective."),
    ])

    with patch("app.agents.orchestrator._get_client", return_value=mock_client), \
         patch("app.agents.orchestrator.settings") as s:
        s.use_mock = False
        s.anthropic_api_key = "sk-test"
        s.claude_model = "claude-3-haiku-20240307"
        s.max_response_tokens = 512

        result = await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Why?",
                conversation_history=[],
            )
        )

    assert result == "I was in the kitchen, Detective."
    assert mock_client.messages.create.call_count == 3


@pytest.mark.asyncio
async def test_tool_results_sent_back_as_user_message(scenario, butler, session):
    """
    After a tool call the orchestrator must include a 'user' message with
    tool_result content in the follow-up API call.
    """
    calls: list[list[dict]] = []
    final = _make_text_response("Final answer.")

    async def capture_create(**kwargs):
        calls.append(kwargs["messages"])
        if len(calls) == 1:
            return _make_tool_response(
                "check_consistency", "tid",
                {"draft_response": "x", "prior_statements": [], "suspect_id": "butler"},
            )
        return final

    mock_client = AsyncMock()
    mock_client.messages.create = capture_create

    with patch("app.agents.orchestrator._get_client", return_value=mock_client), \
         patch("app.agents.orchestrator.settings") as s:
        s.use_mock = False
        s.anthropic_api_key = "sk-test"
        s.claude_model = "claude-3-haiku-20240307"
        s.max_response_tokens = 512

        await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Where were you?",
                conversation_history=[],
            )
        )

    # Second call's messages should include the tool_result
    second_call_messages = calls[1]
    last_user_turn = next(
        m for m in reversed(second_call_messages)
        if m["role"] == "user" and isinstance(m["content"], list)
    )
    assert any(c.get("type") == "tool_result" for c in last_user_turn["content"])


@pytest.mark.asyncio
async def test_max_tool_rounds_safety_cap(scenario, butler, session):
    """
    If Claude never stops calling tools, the orchestrator exits after
    _MAX_TOOL_ROUNDS and yields nothing (rather than looping forever).
    """
    # Always return tool_use — never a text response
    tool_resp = _make_tool_response(
        "check_consistency", "t1",
        {"draft_response": "x", "prior_statements": [], "suspect_id": "butler"},
    )
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=tool_resp)

    with patch("app.agents.orchestrator._get_client", return_value=mock_client), \
         patch("app.agents.orchestrator.settings") as s:
        s.use_mock = False
        s.anthropic_api_key = "sk-test"
        s.claude_model = "claude-3-haiku-20240307"
        s.max_response_tokens = 512

        result = await _collect(
            stream_character_response(
                scenario=scenario,
                suspect=butler,
                session=session,
                player_message="Tell me everything.",
                conversation_history=[],
            )
        )

    # Exhausted rounds — no tokens yielded, no infinite loop
    assert result == ""
    from app.agents import orchestrator as orc
    assert mock_client.messages.create.call_count == orc._MAX_TOOL_ROUNDS


# ── _dispatch_tool ────────────────────────────────────────────────────────────

class TestDispatchTool:

    def test_dispatches_check_consistency(self):
        result = _dispatch_tool("check_consistency", {
            "draft_response": "I was in the kitchen.",
            "prior_statements": [],
            "suspect_id": "butler",
        })
        assert "passed" in result
        assert "contradictions" in result

    def test_dispatches_get_pressure_level(self):
        result = _dispatch_tool("get_pressure_level", {
            "player_message": "Where were you?",
            "conversation_history": [],
            "current_pressure": 0,
        })
        assert "pressure_delta" in result
        assert "reasoning" in result

    def test_dispatches_extract_clues(self):
        result = _dispatch_tool("extract_clues", {
            "response_text": "I was in the kitchen at midnight.",
            "suspect_id": "butler",
            "turn_number": 1,
        })
        assert "clues" in result
        assert isinstance(result["clues"], list)

    def test_unknown_tool_returns_error(self):
        result = _dispatch_tool("nonexistent_tool", {})
        assert "error" in result

    def test_extract_clues_serialises_to_dicts(self):
        """extract_clues result must be JSON-serialisable (dicts, not objects)."""
        result = _dispatch_tool("extract_clues", {
            "response_text": "The decanter was on the table at 11 PM.",
            "suspect_id": "butler",
            "turn_number": 2,
        })
        # Each clue should be a dict (model_dump applied)
        for clue in result["clues"]:
            assert isinstance(clue, dict)
            assert "clue_id" in clue
