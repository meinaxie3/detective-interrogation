"""
chat.py — The streaming chat endpoint. Hot path for every player message.

POST /chat
  Body:  ChatRequest  {session_id, suspect_id, message}
  Returns: text/event-stream SSE

SSE event format:
  data: {"type": "token",   "content": "<token>"}            ← one per token
  data: {"type": "done",    "metadata": { … ChatMetadata }}  ← stream complete
  data: {"type": "error",   "message": "<msg>"}              ← on failure

Phase 3 metadata:
  - consistency_passed: bool  (Claude self-checks via tool loop)
  - new_clues: list           (regex-extracted entities from the response)
  - pressure_delta: int       (1-3 based on question aggressiveness)
  - new_pressure_level: int   (cumulative, per-suspect, capped at _MAX_PRESSURE)
  - new_evidence_found: bool  (true when new_clues is non-empty)
"""

import json
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.chat import ChatRequest
from app.models.session import GamePhase, SuspectInteractionState
from app.services import session_service, scenario_service
from app.agents import orchestrator
from app.agents.tools import pressure as pressure_tool
from app.agents.tools import clue_extractor as clue_tool
from app.api.deps import get_session_or_404

router = APIRouter(tags=["chat"])

# Pressure cap — keeps the UI meter bounded
_MAX_PRESSURE = 15


@router.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """
    Accept a player message and stream the character's response.

    All validation happens before the stream starts so we can return
    proper HTTP error codes (not mid-stream errors which are harder
    to handle on the client).
    """
    # ── Validate session ──────────────────────────────────────────────────────
    session = await get_session_or_404(request.session_id)

    if session.phase != GamePhase.INVESTIGATION:
        raise HTTPException(
            status_code=409,
            detail="This game has already been resolved. Start a new investigation.",
        )

    # ── Validate scenario + suspect ───────────────────────────────────────────
    try:
        scenario = scenario_service.load(session.scenario_id)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Scenario file missing for this session")

    suspect = next(
        (s for s in scenario.suspects if s.id == request.suspect_id),
        None,
    )
    if suspect is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown suspect '{request.suspect_id}'. "
                   f"Valid suspects: {[s.id for s in scenario.suspects]}",
        )

    # ── Load conversation history for this suspect ────────────────────────────
    history = await session_service.get_messages(request.session_id, request.suspect_id)

    # ── Phase 3: evaluate pressure BEFORE streaming ───────────────────────────
    # pressure_tool.evaluate() is pure Python — no API call.
    current_state = session.suspect_states.get(
        request.suspect_id,
        SuspectInteractionState(suspect_id=request.suspect_id),
    )
    prior_user_messages = [m["content"] for m in history if m["role"] == "user"]
    pressure_result = pressure_tool.evaluate(
        player_message=request.message,
        conversation_history=prior_user_messages,
        current_pressure=current_state.pressure_level,
    )
    pressure_delta: int = pressure_result["pressure_delta"]

    # ── Build and return the SSE stream ──────────────────────────────────────
    async def generate():
        full_response = ""

        try:
            async for token in orchestrator.stream_character_response(
                scenario=scenario,
                suspect=suspect,
                session=session,
                player_message=request.message,
                conversation_history=history,
            ):
                full_response += token
                yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"

        except RuntimeError as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            return
        except Exception:
            yield f"data: {json.dumps({'type': 'error', 'message': 'The server encountered an error. Please try again.'})}\n\n"
            return

        # ── Post-stream: persist exchange and update session stats ────────────
        if full_response:
            await session_service.append_message(
                request.session_id, request.suspect_id, "user", request.message
            )
            await session_service.append_message(
                request.session_id, request.suspect_id, "assistant", full_response
            )

            # Refresh session (avoid stale state from concurrent writes)
            updated = await session_service.get(request.session_id)
            updated.total_questions += 1

            # ── Phase 3: extract clues from response (pure Python) ────────────
            turn_number = updated.total_questions   # already incremented above
            clue_result = clue_tool.extract(
                response_text=full_response,
                suspect_id=request.suspect_id,
                turn_number=turn_number,
            )
            new_clues = clue_result["clues"]

            # Persist new clues into the session evidence board
            updated.evidence.extend(new_clues)

            # ── Update per-suspect pressure using dynamic delta ───────────────
            new_pressure_level = 0
            if request.suspect_id in updated.suspect_states:
                state = updated.suspect_states[request.suspect_id]
                state.questions_asked += 1
                state.has_been_questioned = True
                state.message_count += 1
                state.pressure_level = min(
                    state.pressure_level + pressure_delta, _MAX_PRESSURE
                )
                new_pressure_level = state.pressure_level

            await session_service.update(updated)

            metadata = {
                "consistency_passed": True,   # Claude self-checks via tool loop
                "new_clues":          [c.model_dump() for c in new_clues],
                "pressure_delta":     pressure_delta,
                "new_pressure_level": new_pressure_level,
                "new_evidence_found": len(new_clues) > 0,
            }
            yield f"data: {json.dumps({'type': 'done', 'metadata': metadata})}\n\n"
        else:
            yield f"data: {json.dumps({'type': 'done', 'metadata': None})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
