# Detective Interrogation Game — Phase 0 Plan

## What This Is
A text-based detective game where an AI plays multiple suspects in a crime.
The player interrogates them through a chat interface, collects evidence, and
makes an accusation. Each suspect maintains a consistent cover story with real
alibi holes. Getting a suspect to crack requires targeted, pressure-building questions.

Full architecture diagram: `docs/architecture.html`

---

## Project Structure

```
detective-interrogation/
├── backend/              FastAPI Python API
├── frontend/             Next.js React app
├── docs/                 Architecture diagrams
└── PLAN.md               This file
```

---

## Backend (`backend/`)

### `app/models/` — Data Contracts (implement first)
The Pydantic models that define every piece of data in the system.
Nothing else is built until these are solid — tests run against them directly.

| File | Purpose |
|---|---|
| `scenario.py` | `ScenarioModel`, `SuspectModel`, `CrimeModel` — the hidden truth |
| `session.py` | `GameSessionModel`, `SuspectInteractionState`, `ExtractedClue` — live game state |
| `chat.py` | `ChatRequest`, `ChatMetadata`, `AccuseRequest`, `AccuseResponse` — API payloads |
| `game.py` | `NewGameRequest/Response`, `SuspectSummary` — game lifecycle payloads |

### `app/agents/` — AI Logic
The Claude API layer. Isolated from routes so it can be tested independently.

| File | Purpose |
|---|---|
| `orchestrator.py` | Builds prompts, runs tool loop, streams responses |
| `tools/consistency.py` | Tool: check if draft response contradicts prior statements |
| `tools/clue_extractor.py` | Tool: extract named entities from a response as structured JSON |
| `tools/pressure.py` | Tool: evaluate how much pressure a player question applies |

**Key design rule:** The orchestrator is the only place that calls the Claude API.
Routes call the orchestrator; they never touch `anthropic.Anthropic` directly.

### `app/services/` — Business Logic
Stateless functions that mediate between routes and storage.
No Claude API calls here — just data in/out.

| File | Purpose |
|---|---|
| `scenario_service.py` | Load and parse scenario JSON files from disk |
| `session_service.py` | Redis CRUD for sessions + conversation memory per suspect |
| `game_service.py` | Orchestrate a full game turn (call agent, update session, return metadata) |

### `app/prompts/` — Prompt Templates
All prompt strings live here — not in the agent or service files.
This makes it easy to iterate on prompts without touching logic.

| File | Purpose |
|---|---|
| `character_system.py` | Build the per-turn system prompt for a character agent |
| `resolution.py` | Prompt for the end-game reveal narrative |

### `app/api/routes/` — HTTP Endpoints

| File | Endpoints |
|---|---|
| `game.py` | `POST /new-game`, `GET /session/{session_id}` |
| `chat.py` | `POST /chat` (SSE streaming) |
| `accuse.py` | `POST /accuse` |

### `app/core/` — Infrastructure
| File | Purpose |
|---|---|
| `config.py` | Settings loaded from `.env` (API keys, Redis URL, TTL) |
| `redis.py` | Async Redis connection pool |

### `backend/scenarios/` — Scenario Files
JSON files following the `ScenarioModel` schema. One file per scenario.
The scenario service loads these at game-start time.

- `manor_1920.json` — The Ashworth Manor Affair (hardcoded Phase 1 scenario)

---

## Frontend (`frontend/`)

### `src/components/` — UI Components
Split into four domain folders matching the game's UI panels.

| Folder | Components |
|---|---|
| `chat/` | `ChatPanel`, `MessageBubble`, `ChatInput` |
| `suspects/` | `SuspectBoard`, `SuspectCard`, `PressureMeter` |
| `evidence/` | `EvidenceBoard`, `ClueTag` |
| `accusation/` | `AccusationModal`, `ResolutionScene` |

### `src/stores/` — Zustand State
| File | State |
|---|---|
| `gameStore.ts` | Session, suspects list, active suspect, phase, messages per suspect |
| `evidenceStore.ts` | Extracted clues grouped by suspect; de-duplication logic |

### `src/hooks/` — Custom Hooks
| File | Responsibility |
|---|---|
| `useChat.ts` | POST message → parse SSE stream → update store token by token |
| `useGame.ts` | new game, switch suspect, submit accusation |

### `src/lib/` — Utilities
| File | Purpose |
|---|---|
| `types.ts` | TypeScript types mirroring backend Pydantic models |
| `api.ts` | Fetch wrapper for all backend endpoints |

### `src/app/` — Next.js App Router Pages
| Route | Page |
|---|---|
| `/` | Home: start new game or pick scenario |
| `/game/[sessionId]` | Main game: chat + suspect board + evidence locker |

---

## Tests

### What to run right now (Phase 0 — no implementation needed):
```bash
cd backend
pip install -r requirements.txt
pytest tests/unit/test_scenario_validation.py -v
pytest tests/unit/test_models.py -v
pytest tests/unit/test_tools.py -v -k "tool_definition"   # only the definition shape tests
```

These tests verify:
- The scenario JSON is structurally valid
- Pydantic models enforce their contracts
- Claude tool definition dicts have the right shape

### Test categories

| Category | File(s) | Requires | Run when |
|---|---|---|---|
| Scenario integrity | `test_scenario_validation.py` | Nothing | Always — before any session |
| Model contracts | `test_models.py` | Nothing | Always |
| Tool definitions | `test_tools.py` (non-skip) | Nothing | Always |
| Prompt construction | `test_prompts.py` | Phase 1 impl | After `prompts/` is built |
| Tool behaviour | `test_tools.py` (skipped) | Phase 3 impl | After tools are wired |
| Full game flow | `test_game_flow.py` | Phase 1 + Redis | `INTEGRATION=true` |

---

## Implementation Phases

| Phase | Milestone | Key files to implement |
|---|---|---|
| **1** | Core chat loop | `scenario_service.py`, `session_service.py`, `orchestrator.py`, `character_system.py`, `/chat` route, minimal Next.js UI |
| **2** | Multi-suspect | `/new-game`, `/session`, suspect switching, Redis memory per suspect, Zustand store |
| **3** | Consistency + evidence | All three tools, evidence board UI, pressure meter |
| **4** | Accusation + resolution | `/accuse`, `resolution.py`, `ResolutionScene` component, scoring |
| **5** | Dynamic generation + polish | AI scenario generator, difficulty modes, hint system, deploy |

---

## Environment Variables (`.env` in `backend/`)
```
ANTHROPIC_API_KEY=sk-ant-...
REDIS_URL=redis://localhost:6379
SESSION_TTL_SECONDS=7200
DEFAULT_SCENARIO_ID=manor_1920
```
