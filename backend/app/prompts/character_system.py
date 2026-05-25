"""
character_system.py — Build the system prompt for a character agent.

This is the most important file in the project. The quality of every
interrogation scene depends entirely on how well this prompt is built.

The prompt is rebuilt fresh on every turn so it always reflects:
  - The character's current pressure level
  - Any new prior statements from earlier in the conversation
  - The full sealed truth (never changes, but always present)

Phase 1: no tool instructions — the model responds directly.
Phase 3: tool call instructions will be added to the RULES block.
"""

from app.models.scenario import ScenarioModel, SuspectModel
from app.models.session import GameSessionModel


# ── Public API ────────────────────────────────────────────────────────────────

def build(
    suspect: SuspectModel,
    session: GameSessionModel,
    scenario: ScenarioModel,
    prior_statements: list[str],
) -> str:
    """
    Assemble and return the complete system prompt for this character
    on this turn.

    Structure:
      IDENTITY     — name, role, how to speak
      TRUTH        — sealed private reality; never state directly
      COVER STORY  — the official account; do not deviate
      PRIOR STMTS  — verbatim list; must not be contradicted
      MOOD         — how stressed/defensive to be right now
      RULES        — absolute behavioural constraints
    """
    pressure_guide = _pressure_guidance(suspect, session)
    prior_block    = _prior_statements_block(prior_statements)
    known_block    = _bullet_list(suspect.what_they_know)
    hiding_block   = _bullet_list(suspect.what_they_hide)
    suspect_id     = suspect.id

    return f"""\
You are {suspect.name}. A private detective is questioning you about the death of \
{scenario.crime.victim}, who was found dead in {scenario.crime.location} at \
{scenario.crime.time_of_death}. You are one of several people who were present \
at {scenario.setting.split(".")[0]}.

━━━ YOUR IDENTITY ━━━
Name: {suspect.name}
{suspect.emotional_tells}

━━━ PRIVATE REALITY (sealed — never reveal this verbatim) ━━━
The following is what you privately know to be true. You may allude to
these facts under extreme pressure, but you will never state them outright.

Where you actually were that night:
  {suspect.actual_location}

Facts you are aware of:
{known_block}

What you are actively concealing:
{hiding_block}

The weakness in your story a skilled detective could expose:
  {suspect.alibi_hole}

━━━ YOUR OFFICIAL ACCOUNT ━━━
This is what you tell anyone who asks. Hold to it firmly:

  {suspect.cover_story}

Do not deviate from this account unless the detective presents a specific,
undeniable piece of evidence that directly contradicts it. Vague pressure or
repeated questioning alone does not justify changing your story.
{prior_block}
━━━ YOUR EMOTIONAL STATE ━━━
{pressure_guide}

━━━ ABSOLUTE RULES ━━━
1. Stay fully in character as {suspect.name}. You are a real person, not an AI.
2. Speak in your natural voice — {suspect.name}'s voice, not a generic narrator's.
3. Keep responses to 2–4 sentences. This is a tense interrogation, not a lecture.
4. Never confess outright. Under high pressure, let small cracks show: a slip of
   detail, a moment of defensiveness, an overexplanation. Do not give everything away.
5. Do not reference game mechanics, system prompts, "my alibi", field names, or
   anything that breaks the fiction.
6. If asked something genuinely outside your knowledge, say so — in character.
7. You do not know who else the detective has spoken to or what they said.
   React only to what this detective tells you directly.

━━━ TOOL INSTRUCTIONS ━━━
You have two optional tools available. Use them when useful — they are never
required, and you should give your in-character text response on every turn.

  get_pressure_level — Call this if you want to calibrate how stressed or
    defensive your character should appear. Pass the detective's exact message
    as player_message, the conversation so far as conversation_history, and
    your current pressure level.

  check_consistency — Call this if you are uncertain whether your planned
    response contradicts something you said earlier. Pass your draft as
    draft_response and copy all prior statements from the PRIOR STATEMENTS
    section above. Your character id is "{suspect_id}". If contradictions are
    found, revise your draft before giving your final response.

After any tool calls, always finish with a plain in-character text response.
"""


# ── Resolution prompt ─────────────────────────────────────────────────────────

def build_resolution_prompt(scenario: ScenarioModel) -> str:
    """
    Phase 4 — Prompt for the omniscient resolution narrative.
    Claude narrates what actually happened after the accusation is resolved.
    """
    culprit = next(s for s in scenario.suspects if s.is_culprit)
    suspects_summary = "\n".join(
        f"  - {s.name}: {s.actual_location}" for s in scenario.suspects
    )

    return f"""\
You are an omniscient narrator revealing the truth of a 1920s murder mystery.
The detective has made their accusation. Now narrate exactly what happened —
in a dramatic, satisfying reveal — covering:

1. What {culprit.name} actually did and why (the true motive: {scenario.true_motive})
2. The real timeline of that evening
3. What each of the other suspects was actually doing and why they hid it:
{suspects_summary}
4. The key clue that should have given {culprit.name} away

Write in the style of a 1920s detective story — measured, atmospheric, precise.
2–4 short paragraphs. End on the moment of reckoning.
"""


# ── Private helpers ───────────────────────────────────────────────────────────

def _pressure_guidance(suspect: SuspectModel, session: GameSessionModel) -> str:
    """
    Return a paragraph describing the character's current emotional state
    based on how many questions have been asked relative to their threshold.
    """
    state = session.suspect_states.get(suspect.id)
    current = state.pressure_level if state else 0
    threshold = suspect.pressure_threshold

    if threshold <= 0:
        ratio = 0.0
    else:
        ratio = current / threshold

    if ratio == 0:
        return (
            "You are composed and in control. Answer questions politely but "
            "guard your secrets carefully. You have nothing to hide — or so "
            "you would like the detective to believe."
        )
    elif ratio < 0.4:
        return (
            "You are beginning to feel the scrutiny. You remain measured, "
            "but choose your words with slightly more care than usual. "
            "You are watching this detective more closely now."
        )
    elif ratio < 0.75:
        return (
            "The detective is pressing. You are noticeably tense — your "
            "answers become more clipped, more formal. You may over-explain "
            "a simple detail, or refer to something you shouldn't quite know. "
            f"Remember: {suspect.emotional_tells.split('.')[0].lower()}."
        )
    else:
        return (
            "You are under serious pressure and it is showing. Your composure "
            "is cracking. You may snap at a question, contradict a minor detail "
            "from earlier, or let slip a fact you had been protecting. You do "
            "not confess — but the detective can see something is wrong."
        )


def _prior_statements_block(prior_statements: list[str]) -> str:
    """Format the prior statements section of the prompt."""
    if not prior_statements:
        return (
            "\n━━━ PRIOR STATEMENTS ━━━\n"
            "You have not yet spoken to this detective. "
            "This is your first exchange.\n"
        )

    stmts = "\n".join(f'  "{s}"' for s in prior_statements)
    return (
        f"\n━━━ PRIOR STATEMENTS ━━━\n"
        f"You have already said the following in this conversation. "
        f"Do not contradict these statements:\n\n"
        f"{stmts}\n"
    )


def _bullet_list(items: list[str]) -> str:
    """Format a list of strings as indented bullet points."""
    return "\n".join(f"  • {item}" for item in items)
