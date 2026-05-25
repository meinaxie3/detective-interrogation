"""
pressure.py — Claude tool: get_pressure_level

Heuristic implementation — no Claude API calls.

Scores the detective's latest message on a 1-3 pressure scale:
  1 — neutral / fact-gathering ("Where were you?")
  2 — pointed question targeting a specific inconsistency
  3 — direct accusation or contradiction catch ("You're lying — I have a witness")

The orchestrator registers this as a Claude tool.  Claude (playing the
character) calls it to calibrate how stressed/defensive to appear in its
response.  The chat route also calls it directly to compute the authoritative
pressure_delta for the session and the SSE metadata.

Scoring uses two compiled regex passes:
  ACCUSATORY  → delta 3
  POINTED     → delta 2
  (default)   → delta 1
"""

import re
from typing import TypedDict

# ── Tool registration ─────────────────────────────────────────────────────────

TOOL_DEFINITION: dict = {
    "name": "get_pressure_level",
    "description": (
        "Evaluate how much pressure the detective's latest message puts on you. "
        "Return a delta of 1 (neutral), 2 (pointed), or 3 (accusatory/contradiction). "
        "Use this to calibrate how stressed your character should appear."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "player_message": {"type": "string"},
            "conversation_history": {
                "type": "array",
                "items": {"type": "string"}
            },
            "current_pressure": {"type": "integer"}
        },
        "required": ["player_message", "conversation_history", "current_pressure"]
    }
}


# ── Types ─────────────────────────────────────────────────────────────────────

class PressureResult(TypedDict):
    pressure_delta: int    # always 1, 2, or 3
    reasoning: str


# ── Scoring patterns ──────────────────────────────────────────────────────────

# Delta 3 — accusatory, confrontational, or catching a direct lie
_ACCUSATORY = re.compile(
    r"\b("
    r"li(e|ed|es|ar|ars|ing)"
    r"|you\s+did\s+it"
    r"|you\s+kill"
    r"|you\s+poison"
    r"|i\s+know\s+you"
    r"|i\s+have\s+a\s+witness"
    r"|confess"
    r"|caught\s+you"
    r"|revise\s+your\s+statement"
    r"|contradict"
    r"|that's\s+impossible"
    r"|i\s+don'?t\s+believe\s+you"
    r"|prove\s+it"
    r")\b",
    re.IGNORECASE,
)

# Delta 2 — pointed, specific, or pressing for precision
_POINTED = re.compile(
    r"\b("
    r"why"
    r"|explain"
    r"|specifically"
    r"|exact(ly)?"
    r"|precise(ly)?"
    r"|how\s+do\s+you\s+explain"
    r"|what\s+time\s+exactly"
    r"|can\s+you\s+account"
    r"|you\s+(said|told|mentioned|claimed)\s+earlier"
    r"|previously\s+stated"
    r"|cannot\s+be"
    r"|are\s+you\s+(certain|sure)"
    r"|who\s+can\s+confirm"
    r"|signs\s+of"
    r"|i\s+have\s+reason"
    r")\b",
    re.IGNORECASE,
)


# ── Public API ────────────────────────────────────────────────────────────────

def evaluate(
    player_message: str,
    conversation_history: list[str],
    current_pressure: int,
) -> PressureResult:
    """
    Evaluate the pressure delta for *player_message*.

    Args:
        player_message:       The detective's latest question/statement.
        conversation_history: Prior user messages (unused in current heuristic;
                               kept for future multi-turn analysis).
        current_pressure:     The character's current pressure level (unused in
                               current heuristic; available for future weighting).

    Returns:
        {"pressure_delta": int, "reasoning": str}
        pressure_delta is clamped to [1, 3].
    """
    if _ACCUSATORY.search(player_message):
        return {
            "pressure_delta": 3,
            "reasoning": "Direct accusation, confrontation, or contradiction catch.",
        }
    if _POINTED.search(player_message):
        return {
            "pressure_delta": 2,
            "reasoning": "Pointed question targeting a specific detail or inconsistency.",
        }
    return {
        "pressure_delta": 1,
        "reasoning": "Neutral or fact-gathering question.",
    }
