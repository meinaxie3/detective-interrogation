"""
hint_service.py — Generate a contextual investigation hint via Claude.

Phase 5: Called by POST /hint. Claude knows the full truth but only
nudges the detective — it never names the culprit directly.

Falls back to a generic hint if USE_MOCK=true or if Claude fails.
"""

import logging
import anthropic

from app.models.scenario import ScenarioModel
from app.models.session import GameSessionModel
from app.core.config import settings

logger = logging.getLogger(__name__)

_HINT_MAX_TOKENS = 120


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_hint(
    session: GameSessionModel,
    scenario: ScenarioModel,
) -> str:
    """
    Return a contextual hint for the current game state.

    Args:
        session:  Current game session — evidence collected, suspects questioned.
        scenario: Full scenario including hidden truth.

    Returns:
        A hint string (Claude-generated or fallback template).
    """
    if settings.use_mock or not settings.anthropic_api_key:
        return _fallback_hint(session, scenario)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=_HINT_MAX_TOKENS,
            system=_build_prompt(session, scenario),
            messages=[{"role": "user", "content": "Give me a hint."}],
        )

        text = "".join(
            block.text
            for block in response.content
            if hasattr(block, "text") and block.text
        ).strip()

        return text if text else _fallback_hint(session, scenario)

    except Exception as exc:
        logger.warning("Hint generation failed: %s", exc)
        return _fallback_hint(session, scenario)


# ── Private helpers ───────────────────────────────────────────────────────────

def _build_prompt(session: GameSessionModel, scenario: ScenarioModel) -> str:
    culprit = next(s for s in scenario.suspects if s.is_culprit)

    evidence_lines = (
        "\n".join(
            f"  - [{c.category}] \"{c.text}\" (from {c.suspect_id})"
            for c in session.evidence
        )
        if session.evidence
        else "  (none gathered yet)"
    )

    questioned = [
        sid for sid, st in session.suspect_states.items()
        if st.has_been_questioned
    ]
    not_questioned = [s.id for s in scenario.suspects if s.id not in questioned]

    return f"""\
You are a wise, cryptic advisor helping a detective who is stuck.

THE TRUTH — never reveal this directly:
  Culprit: {culprit.name}
  Alibi weakness: {culprit.alibi_hole}
  True motive: {scenario.true_motive}

DETECTIVE'S CURRENT PROGRESS:
  Questions asked: {session.total_questions}
  Evidence gathered:
{evidence_lines}
  Suspects questioned: {', '.join(questioned) if questioned else 'none yet'}
  Not yet questioned: {', '.join(not_questioned) if not_questioned else 'all questioned'}

YOUR TASK:
Write a single short hint (1-2 sentences) that nudges without revealing.
Focus on the most useful next step: an unquestioned suspect, a timeline
gap, or an unexplored contradiction.

Rules:
- Do NOT name {culprit.name} as the culprit.
- Speak like a 1920s private investigator, atmospheric and precise.
- One paragraph only.  No preamble.
"""


def _fallback_hint(session: GameSessionModel, scenario: ScenarioModel) -> str:
    """Generic hint derived from game state — no Claude call."""
    questioned = {
        sid for sid, st in session.suspect_states.items()
        if st.has_been_questioned
    }
    not_questioned = [s for s in scenario.suspects if s.id not in questioned]

    if not_questioned:
        return (
            f"You have not yet spoken to {not_questioned[0].name}. "
            "Every voice in that house carries weight. Leave no stone unturned."
        )

    culprit = next(s for s in scenario.suspects if s.is_culprit)
    state = session.suspect_states.get(culprit.id)
    if state and state.pressure_level < culprit.pressure_threshold // 2:
        return (
            "One suspect has barely been pressed. Push harder — "
            "contradictions surface only under sustained questioning."
        )

    return (
        "Examine the timeline carefully. Someone's account of that evening "
        "does not quite add up. The hour around midnight holds the answer."
    )
