"""
history.py — GET /history endpoint.

Phase 5: Returns all recorded game results, newest first.
Used by the History tab in the frontend to show past scores.
"""

from fastapi import APIRouter
from app.core import history_store
from app.models.history import GameRecord

router = APIRouter(tags=["game"])


@router.get("/history", response_model=list[GameRecord])
async def get_history() -> list[GameRecord]:
    """
    Return all completed game records, newest first.
    Returns an empty list if no games have been played yet.
    """
    return history_store.get_all()
