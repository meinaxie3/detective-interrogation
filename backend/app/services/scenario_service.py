"""
scenario_service.py — Load and validate crime scenarios from JSON files.

Scenarios live in backend/scenarios/<scenario_id>.json.
This is the single place that reads and parses them — nothing else
in the codebase should open scenario files directly.
"""

import json
from pathlib import Path
from app.models.scenario import ScenarioModel

SCENARIOS_DIR = Path(__file__).parent.parent.parent / "scenarios"


def load(scenario_id: str) -> ScenarioModel:
    """
    Load a scenario from disk and validate it against ScenarioModel.

    Raises:
        FileNotFoundError: if no file exists for scenario_id
        pydantic.ValidationError: if the JSON is structurally invalid
    """
    path = SCENARIOS_DIR / f"{scenario_id}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Scenario '{scenario_id}' not found. "
            f"Expected file: {path}"
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return ScenarioModel(**data)


def list_available() -> list[str]:
    """Return scenario_ids of all JSON files present in the scenarios directory."""
    return sorted(p.stem for p in SCENARIOS_DIR.glob("*.json"))
