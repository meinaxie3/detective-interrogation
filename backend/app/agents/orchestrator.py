"""
orchestrator.py — The central AI agent that handles every player message.

Phase 3 implementation: tool loop for consistency + pressure + clue extraction.

Flow per turn (live mode):
  1. Build system prompt (persona + pressure state + prior statements)
  2. Register three Claude tools:
       check_consistency  — Claude self-checks before finalising
       get_pressure_level — Claude calibrates its emotional intensity
       extract_clues      — Claude surfaces evidence in its own words
  3. Run a tool loop:
       a. Call Claude (non-streaming, tool_choice="auto")
       b. If stop_reason == "tool_use": dispatch each tool call, return results
       c. Repeat until Claude gives a text response (stop_reason == "end_turn")
  4. Simulate streaming: yield the final text word-by-word

The orchestrator is the ONLY place in the codebase that instantiates
an Anthropic client.  Routes and services call this module; they never
touch the SDK directly.
"""

import json
from typing import AsyncGenerator
import anthropic

from app.models.scenario import ScenarioModel, SuspectModel
from app.models.session import GameSessionModel
from app.prompts.character_system import build
from app.core.config import settings
from app.agents.mock_responses import stream_mock_response
from app.agents.tools import consistency, pressure, clue_extractor


# ── Tool registry ─────────────────────────────────────────────────────────────
# Only register tools that help Claude shape its in-character response.
# extract_clues is called server-side by the chat route after streaming — Claude
# does not need it here and including it caused spurious extra tool-call rounds.
_TOOLS = [
    consistency.TOOL_DEFINITION,
    pressure.TOOL_DEFINITION,
]

# Safety cap: maximum tool-call rounds before we accept whatever Claude says.
_MAX_TOOL_ROUNDS = 5


# ── Client factory ────────────────────────────────────────────────────────────

def _get_client() -> anthropic.AsyncAnthropic:
    """
    Return a configured async Anthropic client.
    Raises RuntimeError with a helpful message if the API key is missing.
    """
    if not settings.anthropic_api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. "
            "Copy backend/.env.example to backend/.env and add your key."
        )
    return anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _dispatch_tool(name: str, inputs: dict) -> dict:
    """
    Route a Claude tool_use call to the appropriate Python function and
    return the result as a plain dict (serialised to JSON before being
    sent back to Claude).
    """
    if name == "check_consistency":
        return consistency.check(
            draft_response=inputs.get("draft_response", ""),
            prior_statements=inputs.get("prior_statements", []),
            suspect_id=inputs.get("suspect_id", ""),
        )
    if name == "get_pressure_level":
        return pressure.evaluate(
            player_message=inputs.get("player_message", ""),
            conversation_history=inputs.get("conversation_history", []),
            current_pressure=inputs.get("current_pressure", 0),
        )
    if name == "extract_clues":
        result = clue_extractor.extract(
            response_text=inputs.get("response_text", ""),
            suspect_id=inputs.get("suspect_id", ""),
            turn_number=inputs.get("turn_number", 0),
        )
        # Serialise ExtractedClue objects for the JSON round-trip back to Claude
        return {"clues": [c.model_dump() for c in result["clues"]]}
    return {"error": f"Unknown tool: {name}"}


# ── Main entry point ──────────────────────────────────────────────────────────

async def stream_character_response(
    scenario: ScenarioModel,
    suspect: SuspectModel,
    session: GameSessionModel,
    player_message: str,
    conversation_history: list[dict],
) -> AsyncGenerator[str, None]:
    """
    Main entry point.  Yields string tokens as they stream to the caller.

    Phase 3 flow:
      1. Extract prior assistant statements for the system prompt
      2. Build system prompt (persona + hidden truth + prior statements +
         tool instructions)
      3. Run the tool loop until Claude produces a text response
      4. Yield the response word-by-word (simulated streaming — tool-use API
         does not support true token streaming in the same round)

    Mock mode (USE_MOCK=true) skips the tool loop entirely and streams a
    scripted response.  The chat route still runs pressure evaluation and
    clue extraction independently (pure Python, no API call needed).

    Args:
        scenario:             Full scenario including hidden truth.
        suspect:              The specific suspect being interrogated.
        session:              Current game session (pressure level etc.).
        player_message:       The detective's latest question.
        conversation_history: Prior messages for this suspect (user+assistant).
    """
    # ── Mock mode ─────────────────────────────────────────────────────────────
    if settings.use_mock:
        async for token in stream_mock_response(suspect, session, conversation_history):
            yield token
        return

    # ── Live mode — tool loop ─────────────────────────────────────────────────
    prior_statements = [
        m["content"]
        for m in conversation_history
        if m["role"] == "assistant"
    ]

    system_prompt = build(suspect, session, scenario, prior_statements)

    messages: list[dict] = list(conversation_history) + [
        {"role": "user", "content": player_message}
    ]

    client = _get_client()

    for _round in range(_MAX_TOOL_ROUNDS):
        response = await client.messages.create(
            model=settings.claude_model,
            max_tokens=settings.max_response_tokens,
            system=system_prompt,
            messages=messages,
            tools=_TOOLS,
        )

        if response.stop_reason == "tool_use":
            # One or more tool calls — dispatch each and collect results
            tool_results: list[dict] = []
            for block in response.content:
                if block.type == "tool_use":
                    result = _dispatch_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            # Append the assistant turn (tool calls) and our tool results
            messages = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user",      "content": tool_results},
            ]
            # Loop again — Claude will continue

        else:
            # stop_reason == "end_turn" — final text response
            text = "".join(
                block.text
                for block in response.content
                if hasattr(block, "text") and block.text
            )
            if not text.strip():
                # Claude returned end_turn with no text (edge case — treat as
                # exhausted rounds so the chat route handles the empty response)
                return
            # Yield word-by-word to simulate streaming UX
            import asyncio
            words = text.split(" ")
            for i, word in enumerate(words):
                chunk = word if i == len(words) - 1 else word + " "
                yield chunk
                await asyncio.sleep(0)   # yield control to the event loop
            return

    # Exhausted tool rounds without a text response — yield nothing.
    # The chat route handles the empty-response case gracefully.
