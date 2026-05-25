#!/usr/bin/env python3
"""
simulate_game.py — Full end-to-end game simulation.

Runs a complete detective interrogation against the running FastAPI server:
  1.  POST /new-game      — start a fresh game session
  2.  POST /chat ×N       — question each suspect multiple times (streamed)
  3.  POST /accuse        — make the final accusation
  4.  Print full transcript with pressure meters and resolution

Usage:
  cd backend
  python scripts/simulate_game.py

Requires the backend server to be running on port 8000:
  .venv/Scripts/uvicorn app.main:app --reload --port 8000

Works in both USE_MOCK=true and live mode (ANTHROPIC_API_KEY set).
"""

import httpx
import json
import sys
import time

BASE = "http://localhost:8000"
WIDTH = 70   # console width for formatting

# -- ANSI colours --------------------------------------------------------------

AMBER  = "\033[93m"
GREEN  = "\033[92m"
RED    = "\033[91m"
CYAN   = "\033[96m"
DIM    = "\033[2m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def hdr(text: str) -> str:
    return f"{AMBER}{BOLD}{text}{RESET}"

def role_player(text: str) -> str:
    return f"{CYAN}  Detective > {RESET}{text}"

def role_char(name: str, text: str) -> str:
    return f"{GREEN}  {name} > {RESET}{text}"

def pressure_bar(level: int, delta: int = 1, threshold: int = 12) -> str:
    filled = min(level, threshold)
    empty  = threshold - filled
    pct    = level / threshold
    colour = RED if pct >= 0.7 else AMBER if pct >= 0.4 else GREEN
    bar    = colour + "#" * filled + DIM + "." * empty + RESET
    delta_str = f"{DIM}(+{delta}){RESET}" if delta > 1 else ""
    return f"  pressure [{bar}] {level} {delta_str}"


def clue_line(clues: list[dict]) -> str:
    if not clues:
        return ""
    tags = []
    cat_colour = {"time": CYAN, "location": GREEN, "object": AMBER, "person": RED}
    for c in clues:
        col = cat_colour.get(c.get("category", ""), DIM)
        tags.append(f"{col}[{c['category']}] {c['text']}{RESET}")
    return "  evidence: " + "  ".join(tags)

def divider(char: str = "-") -> str:
    return DIM + char * WIDTH + RESET

# -- API helpers ---------------------------------------------------------------

def new_game() -> dict:
    r = httpx.post(f"{BASE}/new-game", json={"scenario_id": "manor_1920"}, timeout=10)
    r.raise_for_status()
    return r.json()


def chat_stream(session_id: str, suspect_id: str, message: str, suspect_name: str) -> tuple[str, int, int, list]:
    """
    POST /chat and stream tokens to stdout.
    Returns (full_response_text, new_pressure_level, pressure_delta, new_clues).
    """
    print(role_player(message))
    print(f"  {DIM}{suspect_name} is thinking…{RESET}", end="", flush=True)

    full_text     = ""
    pressure      = 0
    delta         = 1
    new_clues     = []
    first_token   = True

    with httpx.stream(
        "POST",
        f"{BASE}/chat",
        json={"session_id": session_id, "suspect_id": suspect_id, "message": message},
        timeout=60,
    ) as resp:
        resp.raise_for_status()
        buffer = ""

        for chunk in resp.iter_text():
            buffer += chunk
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                if event["type"] == "token":
                    token = event["content"]
                    if first_token:
                        # Clear the "thinking..." line
                        print(f"\r{' ' * (WIDTH)}\r", end="", flush=True)
                        print(f"  {GREEN}{suspect_name} > {RESET}", end="", flush=True)
                        first_token = False
                    print(token, end="", flush=True)
                    full_text += token

                elif event["type"] == "done":
                    meta = event.get("metadata") or {}
                    pressure  = meta.get("new_pressure_level", 0)
                    delta     = meta.get("pressure_delta", 1)
                    new_clues = meta.get("new_clues", [])
                    print()  # newline after response

                elif event["type"] == "error":
                    print(f"\n{RED}  ERROR: {event['message']}{RESET}")
                    sys.exit(1)

    return full_text, pressure, delta, new_clues


def accuse(session_id: str, suspect_id: str, motive: str, method: str) -> dict:
    r = httpx.post(
        f"{BASE}/accuse",
        json={
            "session_id": session_id,
            "suspect_id": suspect_id,
            "motive":     motive,
            "method":     method,
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


# -- Simulation script ---------------------------------------------------------

INTERROGATION_SCRIPT: list[dict] = [
    # -- Butler (3 questions) ------------------------------------------------
    {"suspect": "butler", "q": "Mr Beckett, where were you between eleven and midnight?"},
    {"suspect": "butler", "q": "Who can confirm you were in the kitchen after Dorothea left at half past eleven?"},
    {"suspect": "butler", "q": "The servant's passage door shows signs of recent use. Can you explain that?"},

    # -- Niece (3 questions) ------------------------------------------------
    {"suspect": "niece",  "q": "Miss Ashworth, you claim you heard nothing — but your room is directly above the study. Is that true?"},
    {"suspect": "niece",  "q": "I have reason to believe you were not in your room all evening. Where were you really?"},
    {"suspect": "niece",  "q": "Did you see anyone near the study that night?"},

    # -- Doctor (2 questions) -----------------------------------------------
    {"suspect": "doctor", "q": "Dr Voss, you left a tonic bottle in the study. Where is that bottle now?"},
    {"suspect": "doctor", "q": "Lord Ashworth mentioned 'a problem with the accounts' during your examination. What did he say exactly?"},

    # -- Butler again — press the weak spot --------------------------------
    {"suspect": "butler", "q": "Beckett, I know you were in the study at eleven forty. I have a witness. Would you like to revise your statement?"},
]

FINAL_ACCUSATION = {
    "suspect_id": "butler",
    "motive":     "embezzlement cover-up",
    "method":     "arsenic in the evening wine",
}


def main() -> None:
    # -- Check server is up ------------------------------------------------
    try:
        health = httpx.get(f"{BASE}/health", timeout=5).json()
    except Exception:
        print(f"{RED}[X] Cannot reach {BASE} — is the server running?{RESET}")
        print(f"  Start it with:  cd backend && .venv/Scripts/uvicorn app.main:app --reload")
        sys.exit(1)

    mode  = "MOCK" if health.get("store") == "memory" and not health.get("phase", 0) else "LIVE"
    # Simpler: check the .env USE_MOCK flag via the health phase field
    import os
    mode = "MOCK" if os.environ.get("USE_MOCK", "").lower() in ("1", "true") else "LIVE"
    print()
    print(divider("="))
    print(hdr("  [>]  THE ASHWORTH MANOR AFFAIR - SIMULATION"))
    print(f"  {DIM}Server: {BASE}  |  Phase {health['phase']}  |  Mode: {mode}{RESET}")
    print(divider("="))

    # -- Start game --------------------------------------------------------
    game     = new_game()
    sess_id  = game["session_id"]
    suspects = {s["id"]: s["name"] for s in game["suspects"]}

    print(f"\n{hdr('  CASE FILE')}")
    print(f"  Session:  {DIM}{sess_id}{RESET}")
    print(f"  Setting:  {game['setting'][:80]}...")
    print(f"  Suspects: {', '.join(suspects.values())}")

    # -- Interrogation loop ------------------------------------------------
    pressures: dict[str, int] = {sid: 0 for sid in suspects}
    current_suspect = None

    for step in INTERROGATION_SCRIPT:
        suspect_id   = step["suspect"]
        suspect_name = suspects[suspect_id]
        question     = step["q"]

        if suspect_id != current_suspect:
            current_suspect = suspect_id
            print(f"\n{divider()}")
            print(hdr(f"  INTERROGATING: {suspect_name.upper()}"))
            print(divider())

        print()
        _, new_pressure, pdelta, pclues = chat_stream(sess_id, suspect_id, question, suspect_name)
        pressures[suspect_id] = new_pressure
        print(pressure_bar(new_pressure, pdelta))
        cl = clue_line(pclues)
        if cl:
            print(cl)
        time.sleep(0.3)

    # -- Accusation --------------------------------------------------------
    print(f"\n{divider('=')}")
    print(hdr("  MAKING ACCUSATION"))
    print(divider("="))
    print(f"  Suspect:  {suspects[FINAL_ACCUSATION['suspect_id']]}")
    print(f"  Motive:   {FINAL_ACCUSATION['motive']}")
    print(f"  Method:   {FINAL_ACCUSATION['method']}")
    print()

    result = accuse(sess_id, **FINAL_ACCUSATION)

    verdict_colour = GREEN if result["is_correct"] else RED
    verdict_word   = "CORRECT" if result["is_correct"] else "WRONG"

    print(divider("="))
    print(f"  {verdict_colour}{BOLD}VERDICT: {verdict_word}{RESET}")
    print(f"  Score:  {result['score']} / 100")
    print(divider())
    print(f"\n{hdr('  THE TRUTH')}")
    print(f"  Culprit: {result['correct_culprit_id']}")
    print(f"  Motive:  {result['correct_motive'][:80]}…")
    print(f"  Method:  {result['correct_method']}")
    print(f"\n{hdr('  RESOLUTION')}")
    # Word-wrap the narrative
    words = result["resolution_narrative"].split()
    line  = "  "
    for word in words:
        if len(line) + len(word) + 1 > WIDTH:
            print(f"{DIM}{line}{RESET}")
            line = "  " + word + " "
        else:
            line += word + " "
    if line.strip():
        print(f"{DIM}{line}{RESET}")

    print(f"\n{divider('=')}")
    print(hdr("  SIMULATION COMPLETE"))
    print(f"  Total questions: {len(INTERROGATION_SCRIPT)}")
    print(f"  Final score:     {result['score']} / 100")
    print(f"  Result:          {'[OK] SOLVED' if result['is_correct'] else '[X] UNSOLVED'}")
    print(divider("="))
    print()


if __name__ == "__main__":
    main()
