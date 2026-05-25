"""
session.py — Game session state stored in Redis.

One session = one game. Created when the player starts a new game.
Serialized to JSON and stored under key: session:{session_id}

The session tracks everything the player has done so far:
- Which suspects they've talked to
- What evidence has been auto-extracted
- Per-suspect pressure levels (how hard they've pushed)
- Whether an accusation has been made
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional
from enum import Enum
import uuid


class GamePhase(str, Enum):
    INVESTIGATION = "investigation"   # Player is interrogating suspects
    ACCUSATION    = "accusation"      # Player has locked in an accusation
    RESOLVED      = "resolved"        # Game is over, reveal shown


class ExtractedClue(BaseModel):
    """A single clue auto-tagged from a suspect's response."""
    clue_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    suspect_id: str      # Which suspect mentioned this
    text: str            # The clue text (e.g. "library", "11:30 PM")
    category: str        # "location" | "time" | "person" | "object"
    turn: int            # Which turn number it was extracted on


class SuspectInteractionState(BaseModel):
    """Tracks the interrogation state for one suspect."""
    suspect_id: str
    questions_asked: int = 0
    pressure_level: int = 0       # Increases each turn; triggers slips at threshold
    has_been_questioned: bool = False
    message_count: int = 0        # Total messages in this suspect's chat


class AccusationModel(BaseModel):
    """The player's final accusation."""
    suspect_id: str
    motive: str
    method: str


class GameSessionModel(BaseModel):
    """
    Full session state. Serialized to Redis on every turn.
    TTL in Redis: 2 hours (configurable).
    """
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario_id: str
    difficulty: str = "medium"          # "easy" | "medium" | "hard"
    phase: GamePhase = GamePhase.INVESTIGATION

    # Per-suspect tracking — keyed by suspect_id
    suspect_states: Dict[str, SuspectInteractionState] = {}

    # Evidence board
    evidence: List[ExtractedClue] = []
    total_questions: int = 0          # Total across all suspects (score input)

    # Accusation (None until player submits)
    accusation: Optional[AccusationModel] = None
    is_correct: Optional[bool] = None  # Set after /accuse is resolved
