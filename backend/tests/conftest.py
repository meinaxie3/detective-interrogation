"""
conftest.py — Shared pytest fixtures and configuration.

Fixtures defined here are available to ALL tests without importing.

Fixture layers:
  - scenario()         → Loaded ScenarioModel from manor_1920.json (unit tests)
  - session()          → Fresh GameSessionModel (unit tests)
  - butler() / niece() → Individual SuspectModel objects (unit tests)
  - app()              → FastAPI TestClient (integration tests — requires INTEGRATION=true)
  - redis_client()     → Real Redis connection (integration tests)
"""

import pytest
import json
from pathlib import Path
from app.models.scenario import ScenarioModel
from app.models.session import GameSessionModel, SuspectInteractionState

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


@pytest.fixture(scope="session")
def scenario() -> ScenarioModel:
    """Load and validate the manor_1920 scenario once per test session."""
    data = json.loads((SCENARIOS_DIR / "manor_1920.json").read_text())
    return ScenarioModel(**data)


@pytest.fixture
def session(scenario) -> GameSessionModel:
    """Fresh game session with all suspects initialised at zero pressure."""
    s = GameSessionModel(scenario_id=scenario.scenario_id)
    for suspect in scenario.suspects:
        s.suspect_states[suspect.id] = SuspectInteractionState(suspect_id=suspect.id)
    return s


@pytest.fixture
def butler(scenario) -> object:
    return next(s for s in scenario.suspects if s.id == "butler")


@pytest.fixture
def niece(scenario) -> object:
    return next(s for s in scenario.suspects if s.id == "niece")


@pytest.fixture
def doctor(scenario) -> object:
    return next(s for s in scenario.suspects if s.id == "doctor")
