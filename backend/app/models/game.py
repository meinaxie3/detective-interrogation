"""
game.py — Request/response models for game lifecycle endpoints.

Covers: POST /new-game and GET /session/{session_id}
These are used once per game, not on every turn.
"""

from pydantic import BaseModel
from typing import List
from .session import GameSessionModel


class NewGameRequest(BaseModel):
    """
    POST /new-game
    scenario_id defaults to 'manor_1920'.
    difficulty: "easy" | "medium" | "hard" — affects scoring and pressure.
    """
    scenario_id: str = "manor_1920"
    difficulty:  str = "medium"


class CaseBrief(BaseModel):
    """Key crime facts shown to the player throughout the investigation."""
    victim: str
    location: str
    time_of_death: str
    scenario_title: str
    setting: str          # First two sentences of the flavour briefing


class SuspectSummary(BaseModel):
    """
    Public-facing suspect info returned when a game starts.
    Contains ONLY what the player is allowed to know upfront.
    Hidden fields (alibi_hole, what_they_hide, is_culprit) are NOT included.
    """
    id: str
    name: str
    cover_story: str


class NewGameResponse(BaseModel):
    """Response to POST /new-game — everything the frontend needs to set up the UI."""
    session_id: str
    scenario_title: str
    setting: str           # Detective briefing flavour text
    suspects: List[SuspectSummary]
    case_brief: CaseBrief  # Crime facts shown during investigation


class SessionStateResponse(BaseModel):
    """
    Response to GET /session/{session_id}
    Returns current session state for page reloads / reconnects.
    """
    session: GameSessionModel
    suspects: List[SuspectSummary]
    case_brief: CaseBrief  # Crime facts — also needed on page reload
