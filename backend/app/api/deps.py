"""
deps.py — Shared FastAPI dependencies injected into route handlers.

Phase 1: minimal — just a helper to convert service exceptions into
         proper HTTP responses so routes stay clean.

Phase 2+: will add rate-limiting, auth headers, Redis health checks.
"""

from fastapi import HTTPException
from app.services import session_service
from app.models.session import GameSessionModel


async def get_session_or_404(session_id: str) -> GameSessionModel:
    """
    FastAPI dependency: load a session by ID or raise 404.
    Use with: session: GameSessionModel = Depends(get_session_or_404)
    but routes pass session_id from the request body, so this is called
    manually rather than as an injected dependency in Phase 1.
    """
    try:
        return await session_service.get(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found or expired")
