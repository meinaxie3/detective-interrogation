"""
chat.py — Request/response models for the /chat endpoint.

The chat endpoint is the hot path — called on every player message.
These models define exactly what the frontend sends and what comes back.

Note: the actual character dialogue is streamed via SSE; ChatResponse
carries only the metadata that arrives AFTER the stream completes.
"""

from pydantic import BaseModel
from typing import List, Optional
from .session import ExtractedClue


class ChatRequest(BaseModel):
    """What the frontend sends to POST /chat."""
    session_id: str
    suspect_id: str
    message: str          # The player's question or statement


class ToolCallResult(BaseModel):
    """Internal — results from one Claude tool call during the agent loop."""
    tool_name: str        # "check_consistency" | "extract_clues" | "get_pressure_level"
    passed: Optional[bool] = None      # for consistency check
    clues: Optional[List[ExtractedClue]] = None   # for extract_clues
    pressure_delta: Optional[int] = None           # for get_pressure_level
    new_evidence_found: bool = False


class ChatMetadata(BaseModel):
    """
    Metadata sent as the final SSE event after streaming completes.
    The frontend uses this to update the evidence board and pressure meters
    without needing a separate polling call.
    """
    consistency_passed: bool
    new_clues: List[ExtractedClue]
    pressure_delta: int
    new_pressure_level: int
    new_evidence_found: bool


class AccuseRequest(BaseModel):
    """What the frontend sends to POST /accuse."""
    session_id: str
    suspect_id: str
    motive: str
    method: str


class AccuseResponse(BaseModel):
    """Result of an accusation attempt."""
    is_correct: bool
    correct_culprit_id: str
    correct_motive: str
    correct_method: str
    score: int                # Lower is better (= total questions asked)
    resolution_narrative: str # Claude's reveal of what really happened
