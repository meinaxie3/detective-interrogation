"""
consistency.py — Claude tool: check_consistency

Pure-Python implementation — no additional Claude API calls.

When the orchestrator registers this as a Claude tool, Claude (playing a
suspect) calls it before finalising every response.  We compare the draft
against the character's prior statements and return a list of any
contradictions we can detect with regex.  Claude uses the result to decide
whether to revise its draft.

Detection strategy (approximate, intentionally forgiving):
  1. Time contradictions  — if the draft names a time not seen in any prior
     statement we flag it.  Identical or overlapping times are silent.
  2. Location contradictions — "I was in X" vs a previous "I was in Y" for
     the *same* time window (crude but catches the common case).

Claude's own language understanding does the heavy lifting; this function
exists to give it a concrete signal rather than relying on it to self-audit
from memory alone.
"""

import re
from typing import TypedDict

# ── Tool registration ─────────────────────────────────────────────────────────

TOOL_DEFINITION: dict = {
    "name": "check_consistency",
    "description": (
        "Check whether your draft response contradicts anything you have said "
        "in previous turns. You MUST call this before finalising every response. "
        "If contradictions are found, revise your draft to eliminate them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "draft_response": {
                "type": "string",
                "description": "The response you are about to give the detective."
            },
            "prior_statements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Your complete prior statements from this conversation."
            },
            "suspect_id": {
                "type": "string",
                "description": "Your character id."
            }
        },
        "required": ["draft_response", "prior_statements", "suspect_id"]
    }
}


# ── Types ─────────────────────────────────────────────────────────────────────

class ConsistencyResult(TypedDict):
    passed: bool
    contradictions: list[str]


# ── Regex helpers ─────────────────────────────────────────────────────────────

# Matches "11 PM", "11:30 PM", "11 o'clock", "midnight", "noon",
# "half past eleven", "quarter to twelve"
_TIME_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b"
    r"|\b\d{1,2}\s*(?:AM|PM|o'clock)\b"
    r"|\bmidnight\b"
    r"|\bnoon\b"
    r"|\bhalf\s+past\s+\w+"
    r"|\bquarter\s+(?:to|past)\s+\w+",
    re.IGNORECASE,
)

# "I was in the kitchen" / "I was at the study" etc.
# Captures ONE word only so "kitchen until 11 PM" doesn't get absorbed.
_I_WAS_RE = re.compile(
    r"\bi\s+(?:was|am|were)\s+(?:in|at)\s+(?:the\s+)?([a-z]\w{1,20})\b",
    re.IGNORECASE | re.MULTILINE,
)


def _extract_times(text: str) -> set[str]:
    return {m.group().lower().strip() for m in _TIME_RE.finditer(text)}


def _extract_locations(text: str) -> set[str]:
    return {m.group(1).strip().lower() for m in _I_WAS_RE.finditer(text)}


# ── Public API ────────────────────────────────────────────────────────────────

def check(
    draft_response: str,
    prior_statements: list[str],
    suspect_id: str,
) -> ConsistencyResult:
    """
    Compare *draft_response* against *prior_statements* for obvious factual
    contradictions.  Returns a ConsistencyResult dict.

    Args:
        draft_response:   The character's proposed reply.
        prior_statements: All previous assistant turns in this conversation.
        suspect_id:       The character's id (unused in logic; kept for logging).

    Returns:
        {"passed": bool, "contradictions": list[str]}
        passed=True  → no contradictions detected; safe to use the draft.
        passed=False → at least one contradiction found; Claude should revise.
    """
    if not prior_statements:
        # First turn — nothing to contradict yet.
        return {"passed": True, "contradictions": []}

    contradictions: list[str] = []

    # ── 1. Time contradiction ─────────────────────────────────────────────────
    draft_times = _extract_times(draft_response)
    prior_times: set[str] = set()
    for stmt in prior_statements:
        prior_times.update(_extract_times(stmt))

    if draft_times and prior_times and draft_times.isdisjoint(prior_times):
        contradictions.append(
            f"Time inconsistency: draft mentions {sorted(draft_times)} "
            f"but prior statements mention {sorted(prior_times)}."
        )

    # ── 2. Location contradiction ─────────────────────────────────────────────
    draft_locs = _extract_locations(draft_response)
    prior_locs: set[str] = set()
    for stmt in prior_statements:
        prior_locs.update(_extract_locations(stmt))

    if draft_locs and prior_locs and draft_locs.isdisjoint(prior_locs):
        contradictions.append(
            f"Location inconsistency: draft places you in {sorted(draft_locs)} "
            f"but previously you stated {sorted(prior_locs)}."
        )

    return {
        "passed": len(contradictions) == 0,
        "contradictions": contradictions,
    }
