"""
game_service.py — Orchestrates game lifecycle operations.

Keeps route handlers thin. All game-state logic that touches more than
one service belongs here rather than in the route files.
"""

from app.models.scenario import ScenarioModel
from app.models.session import GameSessionModel, SuspectInteractionState
from app.services import scenario_service, session_service


async def start_new_game(
    scenario_id: str,
    difficulty: str = "medium",
) -> tuple[GameSessionModel, ScenarioModel]:
    """
    Load a scenario, create a fresh session, persist it, and return both.

    Called by POST /new-game.
    Raises FileNotFoundError if scenario_id does not exist on disk.
    """
    scenario = scenario_service.load(scenario_id)

    session = GameSessionModel(scenario_id=scenario_id, difficulty=difficulty)
    for suspect in scenario.suspects:
        session.suspect_states[suspect.id] = SuspectInteractionState(
            suspect_id=suspect.id
        )

    await session_service.create(session)
    return session, scenario
