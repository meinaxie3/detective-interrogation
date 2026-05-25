"""
history.py — Immutable game record model.

Phase 5: A GameRecord is appended to history.json after every /accuse
resolution. The /history endpoint returns these for the History tab.
"""

import uuid
from datetime import datetime, UTC
from pydantic import BaseModel, Field


class GameRecord(BaseModel):
    """
    Snapshot of a completed game.  All fields are set at resolution time
    and never mutated afterwards.
    """
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id: str
    scenario_id: str

    # Outcome
    is_correct: bool
    score: int
    total_questions: int
    difficulty: str = "medium"

    # What the player said
    accused_suspect_id: str
    player_motive: str
    player_method: str

    # The truth (shown in history for review)
    correct_culprit_id: str

    # ISO-8601 timestamp, UTC
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
