"""
clue_extractor.py — Claude tool: extract_clues

Regex-based named-entity extraction — no Claude API calls.

After Claude streams a character response, the chat route calls extract()
on the full response text.  Any meaningful times, locations, objects, or
person names are returned as ExtractedClue objects and forwarded to the
frontend via the ChatMetadata done event.

The TOOL_DEFINITION is also registered with the Claude API so the character
can optionally call it during its tool loop — giving Claude visibility into
what evidence it is surfacing.

Extraction categories:
  "time"     — clock times, midnight, named periods ("half past eleven")
  "location" — named rooms, passages, places relevant to the scenario
  "object"   — physical items that could be evidence (decanter, bottle …)
  "person"   — named individuals other than the suspect themselves
"""

import re
import uuid
from typing import TypedDict

from app.models.session import ExtractedClue

# ── Tool registration ─────────────────────────────────────────────────────────

TOOL_DEFINITION: dict = {
    "name": "extract_clues",
    "description": (
        "After giving your response, extract any specific named entities from it "
        "that could serve as evidence: times, locations, person names, and physical objects. "
        "Only include genuinely meaningful details, not filler words."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "response_text": {"type": "string"},
            "suspect_id":    {"type": "string"},
            "turn_number":   {"type": "integer"}
        },
        "required": ["response_text", "suspect_id", "turn_number"]
    }
}


# ── Types ─────────────────────────────────────────────────────────────────────

class ExtractionResult(TypedDict):
    clues: list[ExtractedClue]


# ── Extraction patterns ───────────────────────────────────────────────────────

_TIME_RE = re.compile(
    r"\b\d{1,2}:\d{2}\s*(?:AM|PM)\b"
    r"|\b\d{1,2}\s*(?:AM|PM|o'clock)\b"
    r"|\bmidnight\b"
    r"|\bnoon\b"
    r"|\bhalf\s+past\s+\w+"
    r"|\bquarter\s+(?:to|past)\s+\w+",
    re.IGNORECASE,
)

# Word / phrase → category for exact-match entities.
# Checked with word-boundary anchors to avoid partial matches.
_LOCATIONS: list[str] = [
    "kitchen", "study", "library", "hallway", "passage",
    "servant's passage", "dining room", "east wing", "west wing",
    "quarters", "garden", "village", "entrance hall", "staircase",
    "cellar", "attic", "stable", "drawing room", "billiard room",
]

_OBJECTS: list[str] = [
    "decanter", "bottle", "tonic", "ledger", "accounts", "wine",
    "glass", "key", "letter", "document", "candle", "lamp", "bag",
    "inventory", "poison", "arsenic",
]

_PERSONS: list[str] = [
    "dorothea", "clara", "beckett", "voss",
    "lord ashworth", "lady ashworth", "constable", "cook",
]


# ── Public API ────────────────────────────────────────────────────────────────

def extract(
    response_text: str,
    suspect_id: str,
    turn_number: int,
) -> ExtractionResult:
    """
    Extract named evidence entities from *response_text*.

    De-duplicates within a single call (same text+category → one clue).
    Does NOT de-duplicate across turns; the session service handles that
    at the evidence-board level.

    Args:
        response_text: The character's full response for this turn.
        suspect_id:    Which suspect gave this response.
        turn_number:   The current turn index (stored on the clue).

    Returns:
        {"clues": list[ExtractedClue]}
    """
    clues: list[ExtractedClue] = []
    seen: set[tuple[str, str]] = set()

    def _add(text: str, category: str) -> None:
        key = (text.lower().strip(), category)
        if key not in seen:
            seen.add(key)
            clues.append(ExtractedClue(
                clue_id=str(uuid.uuid4())[:8],
                suspect_id=suspect_id,
                text=text.strip(),
                category=category,
                turn=turn_number,
            ))

    # Times
    for m in _TIME_RE.finditer(response_text):
        _add(m.group(), "time")

    # Locations, objects, persons — word-boundary exact match
    for word in _LOCATIONS:
        if re.search(r"\b" + re.escape(word) + r"\b", response_text, re.IGNORECASE):
            _add(word, "location")

    for word in _OBJECTS:
        if re.search(r"\b" + re.escape(word) + r"\b", response_text, re.IGNORECASE):
            _add(word, "object")

    for word in _PERSONS:
        if re.search(r"\b" + re.escape(word) + r"\b", response_text, re.IGNORECASE):
            _add(word, "person")

    return {"clues": clues}
