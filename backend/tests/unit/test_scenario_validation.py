"""
test_scenario_validation.py — Unit tests for scenario JSON integrity.

These tests run against the actual scenario files on disk.
They are the first line of defence: if a scenario is malformed,
the whole game breaks. Run these whenever a scenario file is added or changed.

Tests here do NOT require Redis, Claude API, or a running server.
They only need: the JSON files + Pydantic models.
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError
from app.models.scenario import ScenarioModel

SCENARIOS_DIR = Path(__file__).parent.parent.parent / "scenarios"


def load_raw(scenario_id: str) -> dict:
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    return json.loads(path.read_text())


# ── Structural integrity ─────────────────────────────────────────────────────

def test_manor_1920_loads_without_error():
    """The baseline scenario must parse cleanly into ScenarioModel."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    assert scenario.scenario_id == "manor_1920"


def test_scenario_has_exactly_one_culprit():
    """Exactly one suspect must have is_culprit=True. Not zero, not two."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    culprits = [s for s in scenario.suspects if s.is_culprit]
    assert len(culprits) == 1


def test_culprit_id_matches_is_culprit_flag():
    """The culprit_id field on the scenario must match the suspect with is_culprit=True."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    culprit_suspect = next(s for s in scenario.suspects if s.is_culprit)
    assert culprit_suspect.id == scenario.culprit_id


def test_scenario_has_at_least_two_suspects():
    """Need at least two suspects for the game to be interesting."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    assert len(scenario.suspects) >= 2


def test_all_suspects_have_alibi_holes():
    """Every suspect must have a non-empty alibi_hole — the player needs something to find."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    for suspect in scenario.suspects:
        assert suspect.alibi_hole.strip(), f"Suspect {suspect.id} has empty alibi_hole"


def test_all_suspects_have_emotional_tells():
    """Every suspect needs emotional tells so the AI can portray stress correctly."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    for suspect in scenario.suspects:
        assert suspect.emotional_tells.strip(), f"Suspect {suspect.id} has empty emotional_tells"


def test_culprit_has_higher_pressure_threshold_than_innocent():
    """
    The culprit should be harder to break than innocent suspects.
    They've had time to prepare; they're more motivated to hold their story.
    """
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    culprit = next(s for s in scenario.suspects if s.is_culprit)
    innocents = [s for s in scenario.suspects if not s.is_culprit]
    assert all(
        culprit.pressure_threshold > s.pressure_threshold for s in innocents
    ), "Culprit pressure_threshold must exceed all innocents'"


def test_suspects_have_distinct_ids():
    """Suspect IDs must be unique within a scenario."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    ids = [s.id for s in scenario.suspects]
    assert len(ids) == len(set(ids)), "Duplicate suspect IDs found"


def test_suspects_what_they_know_and_hide_are_nonempty():
    """Every suspect must have at least one item in both what_they_know and what_they_hide."""
    data = load_raw("manor_1920")
    scenario = ScenarioModel(**data)
    for suspect in scenario.suspects:
        assert len(suspect.what_they_know) > 0, f"{suspect.id}: what_they_know is empty"
        assert len(suspect.what_they_hide) > 0, f"{suspect.id}: what_they_hide is empty"


# ── Validation should reject bad data ────────────────────────────────────────

def test_rejects_scenario_with_no_culprit():
    """Pydantic validator must reject a scenario where no suspect is the culprit."""
    data = load_raw("manor_1920")
    # Point culprit_id at a non-existent suspect
    data["culprit_id"] = "ghost"
    with pytest.raises(ValidationError):
        ScenarioModel(**data)


def test_rejects_scenario_with_zero_suspects():
    """Pydantic validator must reject a scenario with fewer than 2 suspects."""
    data = load_raw("manor_1920")
    data["suspects"] = []
    with pytest.raises(ValidationError):
        ScenarioModel(**data)


def test_rejects_scenario_with_two_culprits():
    """If two suspects both have is_culprit=True, validation must fail."""
    data = load_raw("manor_1920")
    # Mark all suspects as culprits
    for s in data["suspects"]:
        s["is_culprit"] = True
    with pytest.raises(ValidationError):
        ScenarioModel(**data)
