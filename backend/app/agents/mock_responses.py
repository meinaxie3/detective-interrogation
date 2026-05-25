"""
mock_responses.py — Scripted character responses for USE_MOCK=true mode.

Responses are keyed by (suspect_id, turn_index) where turn_index is the
number of assistant turns already in the conversation history.

They are written to reflect the scenario accurately:
  - Butler (James Beckett) is guilty — starts formal, becomes tense
  - Niece  (Clara Ashworth) is innocent — nervous, hiding hallway visit
  - Doctor (Dr. Harriet Voss) is innocent — clinical, anxious about tonic bottle

Each suspect has 8 scripted turns; beyond that, a pressure-aware fallback is used.
"""

from typing import AsyncGenerator
from app.models.scenario import SuspectModel
from app.models.session import GameSessionModel

# ── Scripted dialogues ────────────────────────────────────────────────────────

_BUTLER: list[str] = [
    # Turn 0 — composed, polite
    "I spent the entire evening in the kitchen, Detective. "
    "The dinner service required my full attention until well past eleven. "
    "I retired to my quarters promptly at eleven o'clock and did not leave them again.",

    # Turn 1 — still controlled
    "His Lordship was in good spirits at dinner, as far as I could observe. "
    "He dined alone, as was his custom on Wednesday evenings. "
    "I served the decanter myself, as I do every evening.",

    # Turn 2 — slight formality creeping in
    "The kitchen inventory is a nightly duty, Detective. "
    "One does not simply abandon it because the hour is late. "
    "Everything was in order by the time I finished.",

    # Turn 3 — slightly clipped, over-precise
    "I am quite certain about the time. Eleven o'clock precisely. "
    "His Lordship's household runs to a strict schedule — that is the way "
    "he preferred things, and I have maintained that standard for nineteen years.",

    # Turn 4 — defensive on finances
    "The accounts are His Lordship's private business, Detective, "
    "and I would not presume to comment on them. "
    "My role is the smooth running of the household. Nothing more.",

    # Turn 5 — rattled, over-explains the servant's passage
    "The servant's passage is used for routine purposes. "
    "Maintenance, linen delivery, the usual household traffic. "
    "I cannot account for what state the door latch was found in — "
    "the junior staff use it throughout the day.",

    # Turn 6 — beginning to crack
    "I — the inventory was complete. I have nothing further to add about the evening. "
    "You are asking the same questions repeatedly and I find it quite irregular, "
    "Detective. Quite irregular indeed.",

    # Turn 7 — near breaking point
    "Very well. I was alone in the kitchen after Dorothea left at half past eleven. "
    "There is nothing sinister in that. A man may finish his duties without "
    "a witness present. That is all I have to say on the matter.",
]

_NIECE: list[str] = [
    # Turn 0 — nervous, vague
    "I was in my room the entire evening, reading. "
    "I didn't come down after dinner — I had a slight headache and wanted quiet. "
    "I'm sorry I can't be of more help.",

    # Turn 1 — deflects toward uncle's finances
    "Uncle Edmund had been under some strain lately, yes. "
    "I overheard raised voices once or twice in recent weeks — something to do "
    "with the estate, I think. I didn't like to pry.",

    # Turn 2 — defensive about sounds
    "I — I don't recall hearing anything unusual. "
    "The manor has its own sounds at night, creaks and such. "
    "I was absorbed in my book. I really couldn't say.",

    # Turn 3 — flustered
    "I'm not sure what time I fell asleep. It was late, I suppose. "
    "My book was a rather long one. Please, I've told you everything I know.",

    # Turn 4 — slips slightly
    "I... there may have been a noise. A sharp sound, like something falling. "
    "I thought it was one of the cats — they get into everything at night. "
    "I didn't think anything of it at the time.",

    # Turn 5 — begins to admit the hallway
    "If I tell you something, you must understand I had nothing to do with "
    "what happened to my uncle. I was in the hallway, briefly, near midnight. "
    "I had been out — I know I shouldn't have — and I was coming back in. "
    "I saw a figure leaving the study. I assumed it was a servant.",

    # Turn 6 — fuller confession
    "I was visiting someone in the village. A private matter. "
    "I know it looks terrible but I swear I had nothing to do with it. "
    "The figure I saw — tall, male, moving quickly. That's all I can tell you.",

    # Turn 7 — confirms butler
    "I didn't see his face clearly. But the build — and the way he moved — "
    "it was familiar. Someone who works in this house. "
    "I've been afraid to say it directly, Detective, but yes. "
    "It looked like Beckett.",
]

_DOCTOR: list[str] = [
    # Turn 0 — clinical, confident
    "I was called at seven in the evening to examine Lord Ashworth for a recurring "
    "chest complaint — nothing life-threatening. I administered a mild sedative tonic "
    "and departed before nine. I returned the following morning when the constable "
    "sent word.",

    # Turn 1 — thorough but slightly over-explaining
    "Lord Ashworth's chest condition was manageable. He'd had it for some years. "
    "The tonic I prescribed was a standard compound — colourless, tasteless, "
    "perfectly safe in the prescribed dose. I've used it for hundreds of patients.",

    # Turn 2 — first hesitation about the bottle
    "I left my bag in the entrance hall while I examined His Lordship in the study. "
    "I... believe I left the tonic bottle on the side table. For his evening dose. "
    "That is standard practice.",

    # Turn 3 — visibly anxious about the bottle
    "The bottle. Yes. I've been thinking about the bottle. "
    "It was a small brown glass vessel, clearly labelled. "
    "If it is missing, I cannot explain that. I truly cannot.",

    # Turn 4 — medical bag log concern
    "My bag log shows the tonic was dispensed. There is no corresponding entry "
    "for its return because I did not retrieve it — Lord Ashworth was to finish "
    "the course. But if the bottle cannot be found now, that is... worrying.",

    # Turn 5 — genuine fear
    "Detective, I need you to understand — both arsenic and my tonic are "
    "colourless liquids. If someone confused them, or if someone used my bottle "
    "to obscure something, I had absolutely no knowledge of it. "
    "I am a physician. I do not harm my patients.",

    # Turn 6 — points toward butler's access
    "Lord Ashworth mentioned something to me during the examination. "
    "He said — and I remember this precisely — 'there is a problem with the accounts.' "
    "He seemed troubled. I didn't press him. I thought it was a business matter.",

    # Turn 7 — conclusive
    "If I were you, Detective, I would ask who in this house had access to "
    "the study wine decanter before dinner. I prescribed a sedative, not a poison. "
    "Someone else introduced arsenic into that decanter, and they needed both "
    "opportunity and knowledge of chemistry. I'd start with Beckett.",
]

_FALLBACKS: dict[str, list[str]] = {
    "butler": [
        "I have nothing further to add, Detective. I have told you everything I know.",
        "You are pressing me on matters I have already addressed. "
        "I was in the kitchen. That is my statement and I stand by it.",
        "I must insist on my account. Every detail I have given you is the truth.",
    ],
    "niece": [
        "I've told you everything I can, Detective. Please, I'm exhausted.",
        "There's nothing more to say. You know what I saw. You know where I was.",
        "Please. I want this to be over.",
    ],
    "doctor": [
        "I've been completely transparent with you. My conscience is clear.",
        "Ask Beckett about the accounts, Detective. That's where your answer lies.",
        "I've told you everything medically relevant. The rest is not my business.",
    ],
}

_SCRIPTS: dict[str, list[str]] = {
    "butler": _BUTLER,
    "niece":  _NIECE,
    "doctor": _DOCTOR,
}


# ── Public API ────────────────────────────────────────────────────────────────

async def stream_mock_response(
    suspect: SuspectModel,
    session: GameSessionModel,
    conversation_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Yield a scripted response token-by-token (word chunks) to simulate streaming.

    Picks the next scripted line based on how many assistant turns have
    already been spoken. Falls back to pressure-aware generic lines once
    the script is exhausted.
    """
    # Count how many assistant turns exist already (= which line to pick next)
    turn_index = sum(1 for m in conversation_history if m["role"] == "assistant")

    script = _SCRIPTS.get(suspect.id, [])
    if turn_index < len(script):
        response = script[turn_index]
    else:
        # Cycle through fallbacks
        fallbacks = _FALLBACKS.get(suspect.id, ["I have nothing more to say."])
        response = fallbacks[turn_index % len(fallbacks)]

    # Stream word-by-word with a tiny pause to simulate network latency
    import asyncio
    words = response.split(" ")
    for i, word in enumerate(words):
        chunk = word if i == len(words) - 1 else word + " "
        yield chunk
        await asyncio.sleep(0.02)   # 20 ms per word ≈ readable streaming pace
