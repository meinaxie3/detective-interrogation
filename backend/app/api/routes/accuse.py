"""
accuse.py — POST /accuse endpoint.

The player submits their final accusation (suspect + motive + method).
The server checks it against the hidden truth and returns a full result
including a Claude-generated resolution narrative.

Phase 4: Claude generates the resolution narrative.
Phase 5: Difficulty-based scoring; game record persisted to history.json.

Scoring by difficulty:
  easy:   base 100 — 1 pt per question  — wrong penalty -20
  medium: base 100 — 2 pts per question — wrong penalty -30  (default)
  hard:   base 100 — 3 pts per question — wrong penalty -40
  Minimum score is always 0.
"""

from fastapi import APIRouter, HTTPException

from app.models.chat import AccuseRequest, AccuseResponse
from app.models.session import GamePhase, AccusationModel
from app.models.history import GameRecord
from app.services import session_service, scenario_service
from app.services import resolution_service
from app.core import history_store
from app.api.deps import get_session_or_404

router = APIRouter(tags=["game"])

# Scoring parameters per difficulty level
_SCORE_PARAMS: dict[str, dict] = {
    "easy":   {"per_q": 1, "wrong_penalty": 20},
    "medium": {"per_q": 2, "wrong_penalty": 30},
    "hard":   {"per_q": 3, "wrong_penalty": 40},
}
_DEFAULT_PARAMS = _SCORE_PARAMS["medium"]


@router.post("/accuse", response_model=AccuseResponse)
async def accuse(request: AccuseRequest) -> AccuseResponse:
    """
    Resolve the player's accusation against the hidden truth.
    Transitions the session to RESOLVED and locks further questioning.
    Appends a GameRecord to history.json for the History tab.
    """
    session = await get_session_or_404(request.session_id)

    if session.phase != GamePhase.INVESTIGATION:
        raise HTTPException(
            status_code=409,
            detail="An accusation has already been made. This investigation is closed.",
        )

    try:
        scenario = scenario_service.load(session.scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Scenario file missing for this session")

    culprit = next(s for s in scenario.suspects if s.is_culprit)

    # ── Evaluate accusation ───────────────────────────────────────────────────
    is_correct = request.suspect_id == scenario.culprit_id

    # ── Score (difficulty-aware) ──────────────────────────────────────────────
    params = _SCORE_PARAMS.get(session.difficulty, _DEFAULT_PARAMS)
    score  = max(0, 100 - session.total_questions * params["per_q"])
    if not is_correct:
        score = max(0, score - params["wrong_penalty"])

    # ── Persist accusation on session ─────────────────────────────────────────
    session.accusation = AccusationModel(
        suspect_id=request.suspect_id,
        motive=request.motive,
        method=request.method,
    )
    session.phase      = GamePhase.RESOLVED
    session.is_correct = is_correct
    await session_service.update(session)

    # ── Persist game record to history ────────────────────────────────────────
    history_store.append(GameRecord(
        session_id=session.session_id,
        scenario_id=session.scenario_id,
        difficulty=session.difficulty,
        is_correct=is_correct,
        score=score,
        total_questions=session.total_questions,
        accused_suspect_id=request.suspect_id,
        player_motive=request.motive,
        player_method=request.method,
        correct_culprit_id=culprit.id,
    ))

    # ── Build resolution narrative (Phase 4: Claude-generated) ────────────────
    player_suspect = next(
        (s for s in scenario.suspects if s.id == request.suspect_id), None
    )
    narrative = await resolution_service.generate_narrative(
        scenario=scenario,
        player_suspect=player_suspect,
        player_motive=request.motive,
        player_method=request.method,
        is_correct=is_correct,
    )

    return AccuseResponse(
        is_correct=is_correct,
        correct_culprit_id=culprit.id,
        correct_motive=scenario.true_motive,
        correct_method=scenario.crime.method,
        score=score,
        resolution_narrative=narrative,
    )
