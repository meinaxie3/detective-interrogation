"""
resolution_service.py — Generate the end-game resolution narrative via Claude.

Phase 4: Called by the /accuse route after the player makes their final
accusation. Claude produces a dramatic, atmospheric reveal in the style
of a 1920s detective story.

Design notes:
  - One-shot, non-streaming call (no tool use needed).
  - Falls back to a minimal template if USE_MOCK=true, if the API key
    is missing, or if Claude raises any exception.
  - Fallback always includes the culprit's name so the existing test
    `assert "Beckett" in data["resolution_narrative"]` never breaks.
  - Resolution max_tokens is deliberately higher than chat responses
    (600 vs 512) because the narrative should be richer and untruncated.
"""

import logging
import anthropic

from app.models.scenario import ScenarioModel, SuspectModel
from app.prompts.resolution import build as build_prompt
from app.core.config import settings

logger = logging.getLogger(__name__)

_RESOLUTION_MAX_TOKENS = 600


# ── Public API ────────────────────────────────────────────────────────────────

async def generate_narrative(
    scenario: ScenarioModel,
    player_suspect: SuspectModel | None,
    player_motive: str,
    player_method: str,
    is_correct: bool,
) -> str:
    """
    Return a resolution narrative for the completed game.

    In mock mode or on any error, returns a simple template string that
    still satisfies the response contract (non-empty, contains culprit name).

    Args:
        scenario:        Full scenario with hidden truth.
        player_suspect:  The suspect the player accused (None if unrecognised).
        player_motive:   The motive the player stated.
        player_method:   The method the player stated.
        is_correct:      Whether the player identified the real culprit.

    Returns:
        A narrative string (Claude-generated or fallback).
    """
    if settings.use_mock or not settings.anthropic_api_key:
        return _fallback(scenario, player_suspect, is_correct)

    try:
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        system_prompt = build_prompt(
            scenario=scenario,
            player_suspect=player_suspect,
            player_motive=player_motive,
            player_method=player_method,
            is_correct=is_correct,
        )

        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=_RESOLUTION_MAX_TOKENS,
            system=system_prompt,
            messages=[
                {"role": "user", "content": "Narrate the resolution."}
            ],
        )

        text = "".join(
            block.text
            for block in response.content
            if hasattr(block, "text") and block.text
        ).strip()

        return text if text else _fallback(scenario, player_suspect, is_correct)

    except Exception as exc:
        logger.warning("Resolution narrative generation failed: %s", exc)
        return _fallback(scenario, player_suspect, is_correct)


# ── Private helpers ───────────────────────────────────────────────────────────

def _fallback(
    scenario: ScenarioModel,
    player_suspect: SuspectModel | None,
    is_correct: bool,
) -> str:
    """
    Minimal template narrative — used in mock mode and as error fallback.
    Always non-empty and always includes the culprit's name.
    """
    culprit  = next(s for s in scenario.suspects if s.is_culprit)
    innocents = [s for s in scenario.suspects if s.id != culprit.id]

    if is_correct:
        opening = (
            f"Your instincts were correct, Detective. {culprit.name} is guilty. "
            f"{scenario.true_motive} "
            f"On the night in question, {culprit.name} gained access to "
            f"{scenario.crime.location} and administered {scenario.crime.method}, "
            f"leaving {scenario.crime.victim} dead by {scenario.crime.time_of_death}."
        )
    else:
        wrong_name = player_suspect.name if player_suspect else "your suspect"
        opening = (
            f"An understandable conclusion, but the wrong one. "
            f"{wrong_name} did not commit this crime. "
            f"The true culprit was {culprit.name}. "
            f"{scenario.true_motive} "
            f"It was {culprit.name} who administered {scenario.crime.method}, "
            f"leaving {scenario.crime.victim} dead by {scenario.crime.time_of_death}."
        )

    reveals = [
        f"{s.name} was hiding that {s.what_they_hide[0].lower()}."
        for s in innocents
        if s.what_they_hide
    ]

    return (
        f"{opening} "
        f"As for the others: {' '.join(reveals)} "
        f"The investigation is now closed."
    )
