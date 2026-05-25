"""
test_prompts.py — Unit tests for system prompt construction.

The system prompt is the most sensitive part of the game. If it leaks
hidden information, the game is broken. If it's missing key context,
the AI gives incoherent responses.

These tests verify that build() produces prompts that contain exactly
the right sections — and critically, that hidden fields never appear
in a form that would break immersion.

All tests run against the real manor_1920 scenario for grounding.
No Claude API calls — just string inspection on the built prompt.
"""

import pytest
import json
from pathlib import Path
from app.models.scenario import ScenarioModel
from app.models.session import GameSessionModel, SuspectInteractionState
from app.prompts.character_system import build

SCENARIOS_DIR = Path(__file__).parent.parent.parent / "scenarios"


@pytest.fixture
def scenario() -> ScenarioModel:
    data = json.loads((SCENARIOS_DIR / "manor_1920.json").read_text())
    return ScenarioModel(**data)


@pytest.fixture
def butler(scenario) -> object:
    return next(s for s in scenario.suspects if s.id == "butler")


@pytest.fixture
def session(scenario) -> GameSessionModel:
    s = GameSessionModel(scenario_id=scenario.scenario_id)
    s.suspect_states["butler"] = SuspectInteractionState(suspect_id="butler")
    return s


# ── Prompt must contain key sections ─────────────────────────────────────────

def test_prompt_contains_character_name(scenario, butler, session):
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "James Beckett" in prompt


def test_prompt_contains_cover_story(scenario, butler, session):
    """Cover story must be present — it's the character's public alibi."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert butler.cover_story in prompt or "kitchen" in prompt.lower()


def test_prompt_contains_emotional_tells(scenario, butler, session):
    """Emotional tells guide the AI's portrayal of stress."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert butler.emotional_tells in prompt or "formal" in prompt.lower()


def test_prompt_contains_prior_statements_section(scenario, butler, session):
    """Prior statements section must exist even when empty, so the AI knows to be consistent."""
    prompt = build(butler, session, scenario, prior_statements=[])
    # The section header should always be present
    assert "prior" in prompt.lower() or "statement" in prompt.lower()


def test_prompt_includes_injected_prior_statements(scenario, butler, session):
    """When prior statements exist, they must appear verbatim in the prompt."""
    priors = ["I was in the kitchen all evening.", "I did not enter the east wing."]
    prompt = build(butler, session, scenario, prior_statements=priors)
    for statement in priors:
        assert statement in prompt


def test_prompt_contains_tool_call_instruction(scenario, butler, session):
    """The prompt must instruct the character to call tools before responding."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "check_consistency" in prompt or "tool" in prompt.lower()


# ── Prompt must NOT leak game mechanics ──────────────────────────────────────

def test_prompt_does_not_contain_field_name_is_culprit(scenario, butler, session):
    """The literal string 'is_culprit' must never appear in the prompt."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "is_culprit" not in prompt


def test_prompt_does_not_contain_field_name_alibi_hole(scenario, butler, session):
    """The field name 'alibi_hole' must never appear — only its value in natural language."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "alibi_hole" not in prompt


def test_prompt_does_not_contain_field_name_pressure_threshold(scenario, butler, session):
    """Game mechanic field names must not leak into the AI's context."""
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "pressure_threshold" not in prompt


def test_prompt_does_not_tell_character_they_are_the_culprit_explicitly(scenario, butler, session):
    """
    The culprit knows what they did, but the prompt should frame it as
    'you poisoned the wine' — not 'you are the culprit' (game-language).
    """
    prompt = build(butler, session, scenario, prior_statements=[])
    assert "is_culprit" not in prompt
    assert "culprit" not in prompt.lower()


# ── Innocent suspect prompt differences ──────────────────────────────────────

def test_innocent_prompt_does_not_include_culprit_truth(scenario, session):
    """An innocent suspect's prompt must not contain the culprit's hidden truth."""
    niece = next(s for s in scenario.suspects if s.id == "niece")
    session.suspect_states["niece"] = SuspectInteractionState(suspect_id="niece")
    prompt = build(niece, session, scenario, prior_statements=[])
    # The butler's embezzlement detail is the culprit's secret — not the niece's to know
    assert "embezzlement ledger" not in prompt
