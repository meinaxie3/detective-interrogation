"""
test_scenario_service.py — Unit tests for scenario_service.

Verifies that the service correctly loads, validates, and lists scenarios.
No I/O beyond the scenarios/ directory. No Claude API. No Redis.
"""

import pytest
from pydantic import ValidationError
from app.services.scenario_service import load, list_available
from app.models.scenario import ScenarioModel


def test_load_manor_returns_scenario_model():
    scenario = load("manor_1920")
    assert isinstance(scenario, ScenarioModel)
    assert scenario.scenario_id == "manor_1920"


def test_load_manor_has_correct_title():
    scenario = load("manor_1920")
    assert "Ashworth" in scenario.title


def test_load_manor_has_three_suspects():
    scenario = load("manor_1920")
    assert len(scenario.suspects) == 3


def test_load_manor_culprit_is_butler():
    scenario = load("manor_1920")
    assert scenario.culprit_id == "butler"


def test_load_raises_for_missing_scenario():
    with pytest.raises(FileNotFoundError, match="nonexistent"):
        load("nonexistent")


def test_load_is_idempotent():
    """Loading the same scenario twice returns equal objects."""
    a = load("manor_1920")
    b = load("manor_1920")
    assert a.model_dump() == b.model_dump()


def test_list_available_contains_manor():
    available = list_available()
    assert "manor_1920" in available


def test_list_available_returns_strings():
    available = list_available()
    assert all(isinstance(s, str) for s in available)


def test_list_available_has_no_extension():
    """IDs should be bare names, not 'manor_1920.json'."""
    available = list_available()
    assert all("." not in s for s in available)
