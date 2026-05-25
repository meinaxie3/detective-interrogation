"""
game.py — Game lifecycle endpoints.

POST /new-game   Create a new session and return public suspect info
GET  /session/{session_id}   Retrieve current session state (for reconnects)
"""

from fastapi import APIRouter, HTTPException
from app.models.game import (
    NewGameRequest, NewGameResponse, SuspectSummary,
    SessionStateResponse, CaseBrief,
)
from app.models.scenario import ScenarioModel
from app.services import game_service, session_service, scenario_service
from app.api.deps import get_session_or_404

router = APIRouter(tags=["game"])


def _make_case_brief(scenario: ScenarioModel) -> CaseBrief:
    """Extract the crime facts the detective is allowed to know."""
    # Trim setting to first two sentences so it's readable in a sidebar
    sentences = scenario.setting.replace("  ", " ").split(". ")
    short_setting = ". ".join(sentences[:2]).strip()
    if short_setting and not short_setting.endswith("."):
        short_setting += "."
    return CaseBrief(
        victim=scenario.crime.victim,
        location=scenario.crime.location,
        time_of_death=scenario.crime.time_of_death,
        scenario_title=scenario.title,
        setting=short_setting,
    )


@router.post("/new-game", response_model=NewGameResponse)
async def new_game(request: NewGameRequest) -> NewGameResponse:
    """
    Start a new game session.

    Loads the requested scenario, creates a session in the store,
    and returns the public-facing suspect list. Hidden fields
    (alibi_hole, actual_location, is_culprit, what_they_hide)
    are never included in the response.
    """
    try:
        session, scenario = await game_service.start_new_game(
            request.scenario_id, request.difficulty
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Scenario '{request.scenario_id}' not found. "
                   f"Check backend/scenarios/ for available scenarios.",
        )

    return NewGameResponse(
        session_id=session.session_id,
        scenario_title=scenario.title,
        setting=scenario.setting,
        suspects=[
            SuspectSummary(id=s.id, name=s.name, cover_story=s.cover_story)
            for s in scenario.suspects
        ],
        case_brief=_make_case_brief(scenario),
    )


@router.get("/session/{session_id}", response_model=SessionStateResponse)
async def get_session(session_id: str) -> SessionStateResponse:
    """
    Return the current session state for a given session ID.
    Used by the frontend on page reload to restore game state.
    """
    session = await get_session_or_404(session_id)

    try:
        scenario = scenario_service.load(session.scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Scenario file missing for this session")

    return SessionStateResponse(
        session=session,
        suspects=[
            SuspectSummary(id=s.id, name=s.name, cover_story=s.cover_story)
            for s in scenario.suspects
        ],
        case_brief=_make_case_brief(scenario),
    )
