"""
resolution.py — Build the resolution prompt for the end-game narrative.

Phase 4: Claude generates a dramatic, atmospheric reveal after the
player makes their final accusation.

The prompt adapts based on:
  - Whether the player identified the correct culprit
  - The motive and method the player proposed
  - The full cast of suspects and what each was actually hiding

This produces a resolution that feels personal to the player's theory,
not just a generic recitation of facts.
"""

from app.models.scenario import ScenarioModel, SuspectModel


def build(
    scenario: ScenarioModel,
    player_suspect: SuspectModel | None,
    player_motive: str,
    player_method: str,
    is_correct: bool,
) -> str:
    """
    Assemble the full resolution system prompt for Claude.

    Claude narrates what actually happened in an atmospheric 1920s
    detective-story voice. If the player was wrong, the narrative gently
    corrects their theory before revealing the truth.

    Args:
        scenario:        Full scenario with hidden truth and all suspects.
        player_suspect:  The suspect the player accused (None if unknown id).
        player_motive:   The motive the player stated in their accusation.
        player_method:   The method the player stated in their accusation.
        is_correct:      True if the player identified the real culprit.

    Returns:
        A string system prompt ready to pass to client.messages.create().
    """
    culprit = next(s for s in scenario.suspects if s.is_culprit)

    suspects_summary = "\n".join(
        f"  - {s.name}: {s.actual_location}"
        for s in scenario.suspects
    )

    player_name = player_suspect.name if player_suspect else "an unnamed individual"

    if is_correct:
        accusation_context = (
            f"The detective correctly identified {culprit.name} as the murderer. "
            f"They proposed the motive as: \"{player_motive}\", "
            f"and the method as: \"{player_method}\". "
            f"Confirm their instincts and fill in the complete truth — "
            f"the details they got right, the ones they missed, and the full story."
        )
    else:
        accusation_context = (
            f"The detective accused {player_name}, but this was incorrect. "
            f"They proposed the motive as: \"{player_motive}\", "
            f"and the method as: \"{player_method}\". "
            f"Gently but firmly correct their mistake before revealing "
            f"the true culprit: {culprit.name}."
        )

    return f"""\
You are an omniscient narrator revealing the truth of a 1920s murder mystery.
The detective has made their final accusation. Your task is to narrate exactly
what happened — dramatic, atmospheric, precise — in the voice of a golden-age
detective novel.

ACCUSATION CONTEXT:
{accusation_context}

YOUR NARRATIVE MUST COVER (in order):
1. Whether the detective was right or wrong, and why
2. What {culprit.name} actually did and why
   (true motive: {scenario.true_motive})
   (true method: {scenario.crime.method})
3. The real movements of every suspect that evening, and why each one
   was hiding something:
{suspects_summary}
4. The single key clue that should have exposed {culprit.name} sooner

STYLE RULES:
- Write in the voice of a 1920s omniscient narrator: measured, atmospheric,
  precise. Short declarative sentences. No modern idiom.
- Exactly 3-4 short paragraphs. No bullet points. No headers.
- End on a moment of moral weight or reckoning.
- The victim's name is {scenario.crime.victim}. Use it at least once.
- Do not address the detective directly. Narrate in the third person.
- Do not break the fiction. You are the narrator, not an AI assistant.
"""
