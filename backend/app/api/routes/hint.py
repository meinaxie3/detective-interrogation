"""
hint.py — POST /hint endpoint.

Phase 5: Generates a contextual, spoiler-free hint for the player
without revealing the culprit. Only available during investigation.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import get_session_or_404
from app.models.session import GamePhase
from app.services import scenario_service
from app.services.hint_service import generate_hint

router = APIRouter(tags=["game"])


class HintRequest(BaseModel):
    session_id: str


class HintResponse(BaseModel):
    hint: str


@router.post("/hint", response_model=HintResponse)
async def hint(request: HintRequest) -> HintResponse:
    """
    Return a contextual investigation hint for the current session.
    Hints are only available during the INVESTIGATION phase.
    """
    session = await get_session_or_404(request.session_id)

    if session.phase != GamePhase.INVESTIGATION:
        raise HTTPException(
            status_code=409,
            detail="Hints are only available during the investigation phase.",
        )

    try:
        scenario = scenario_service.load(session.scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Scenario file missing.")

    hint_text = await generate_hint(session=session, scenario=scenario)
    return HintResponse(hint=hint_text)
