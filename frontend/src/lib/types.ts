/**
 * types.ts — Shared TypeScript types mirroring the backend Pydantic models.
 *
 * Keep this in sync with backend/app/models/*.py.
 * Only contains types that cross the API boundary — internal UI state
 * types live in the Zustand store files.
 */

// ── Scenario / Game Setup ────────────────────────────────────────────────────

/** Key crime facts shown to the player throughout the investigation */
export interface CaseBrief {
  victim: string;
  location: string;
  time_of_death: string;
  scenario_title: string;
  setting: string;
}

/** Returned by POST /new-game */
export interface NewGameResponse {
  session_id: string;
  scenario_title: string;
  setting: string;          // Detective briefing flavour text
  suspects: SuspectSummary[];
  case_brief: CaseBrief;
}

/** Public-facing suspect info — hidden fields stripped by the backend */
export interface SuspectSummary {
  id: string;
  name: string;
  cover_story: string;
}

// ── Chat ─────────────────────────────────────────────────────────────────────

export interface ChatRequest {
  session_id: string;
  suspect_id: string;
  message: string;
}

/**
 * Sent as the final SSE event after the character stream ends.
 * Used to update the evidence board and pressure meters.
 */
export interface ChatMetadata {
  consistency_passed: boolean;
  new_clues: ExtractedClue[];
  pressure_delta: number;
  new_pressure_level: number;
  new_evidence_found: boolean;
}

// ── Evidence ─────────────────────────────────────────────────────────────────

export type ClueCategory = "location" | "time" | "person" | "object";

export interface ExtractedClue {
  clue_id: string;
  suspect_id: string;
  text: string;
  category: ClueCategory;
  turn: number;
}

// ── Session State ─────────────────────────────────────────────────────────────

/** Returned by GET /session/{session_id} */
export interface SessionStateResponse {
  session: GameSession;
  suspects: SuspectSummary[];
  case_brief: CaseBrief;
}


export type GamePhase = "investigation" | "accusation" | "resolved";

export interface SuspectInteractionState {
  suspect_id: string;
  questions_asked: number;
  pressure_level: number;
  has_been_questioned: boolean;
  message_count: number;
}

export interface GameSession {
  session_id: string;
  scenario_id: string;
  phase: GamePhase;
  suspect_states: Record<string, SuspectInteractionState>;
  evidence: ExtractedClue[];
  total_questions: number;
  accusation: Accusation | null;
  is_correct: boolean | null;
}

// ── Accusation ────────────────────────────────────────────────────────────────

export interface Accusation {
  suspect_id: string;
  motive: string;
  method: string;
}

export interface AccuseRequest extends Accusation {
  session_id: string;
}

export interface AccuseResponse {
  is_correct: boolean;
  correct_culprit_id: string;
  correct_motive: string;
  correct_method: string;
  score: number;
  resolution_narrative: string;
}

// ── History ───────────────────────────────────────────────────────────────────

export type Difficulty = "easy" | "medium" | "hard";

/** Returned by GET /history — one record per completed game */
export interface GameRecord {
  record_id: string;
  session_id: string;
  scenario_id: string;
  difficulty: Difficulty;
  is_correct: boolean;
  score: number;
  total_questions: number;
  accused_suspect_id: string;
  player_motive: string;
  player_method: string;
  correct_culprit_id: string;
  timestamp: string;   // ISO-8601
}

// ── Hint ──────────────────────────────────────────────────────────────────────

export interface HintResponse {
  hint: string;
}

// ── SSE Event Types ───────────────────────────────────────────────────────────

/**
 * SSE events streamed from POST /chat.
 * These match the exact wire format the backend sends:
 *   data: {"type":"token",   "content":"…"}
 *   data: {"type":"done",    "metadata":{…}}   ← null if stream was empty
 *   data: {"type":"error",   "message":"…"}
 */
export type SSEEvent =
  | { type: "token";   content: string }
  | { type: "done";    metadata: ChatMetadata | null }
  | { type: "error";   message: string };

// ── Chat UI ───────────────────────────────────────────────────────────────────

export type MessageRole = "player" | "character";

export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  suspect_id: string;
  timestamp: Date;
  isStreaming?: boolean;    // true while tokens are still arriving
}
