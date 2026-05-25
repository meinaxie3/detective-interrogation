/**
 * gameStore.ts — Central Zustand store for all game state.
 *
 * Phase 2 additions:
 *   - suspectStates  — server-authoritative pressure levels per suspect
 *   - evidence       — auto-extracted clues (populated in Phase 3)
 *   - accusationResult — result after POST /accuse
 *   - applyMetadata  — updates pressure from each SSE done event
 *   - setPhase       — transition investigation → resolved
 *   - setAccusationResult — store the resolution screen data
 *
 * One store handles all concerns so evidence, pressure, and accusation
 * can read from the same slice of truth without cross-store subscriptions.
 */

import { create } from "zustand";
import type {
  NewGameResponse,
  SuspectSummary,
  ChatMessage,
  GamePhase,
  ChatMetadata,
  ExtractedClue,
  AccuseResponse,
  SuspectInteractionState,
  Difficulty,
  CaseBrief,
} from "@/lib/types";

// ── State shape ───────────────────────────────────────────────────────────────

interface GameState {
  // Session
  sessionId: string | null;
  scenarioTitle: string;
  setting: string;
  phase: GamePhase;
  difficulty: Difficulty;
  caseBrief: CaseBrief | null;

  // Suspects
  suspects: SuspectSummary[];
  activeSuspectId: string | null;

  // Per-suspect server state (pressure levels, question counts)
  suspectStates: Record<string, SuspectInteractionState>;

  // Chat — one message array per suspect, keyed by suspect_id
  messages: Record<string, ChatMessage[]>;

  // Evidence board (Phase 3 populates this via extract_clues tool)
  evidence: ExtractedClue[];

  // Accusation result — set after POST /accuse resolves
  accusationResult: AccuseResponse | null;

  // UI
  isLoading: boolean;
  error: string | null;
  hint: string | null;
}

// ── Action shape ──────────────────────────────────────────────────────────────

interface GameActions {
  /** Initialise store from a successful /new-game response. */
  startGame: (response: NewGameResponse) => void;

  /** Switch the active suspect. Creates an empty message array if needed. */
  switchSuspect: (suspectId: string) => void;

  /** Append a complete message (player or character) to a suspect's history. */
  appendMessage: (suspectId: string, message: ChatMessage) => void;

  /**
   * Append a streaming token to an in-progress character message.
   * Matches by messageId — only updates the content field.
   */
  appendToken: (suspectId: string, messageId: string, token: string) => void;

  /** Mark a streaming message as complete (sets isStreaming = false). */
  finalizeMessage: (suspectId: string, messageId: string) => void;

  /** Remove a message by ID (used when a stream fails with no content). */
  removeMessage: (suspectId: string, messageId: string) => void;

  /**
   * Apply metadata from the SSE done event.
   * Updates pressure level for the given suspect and appends any new clues.
   */
  applyMetadata: (suspectId: string, metadata: ChatMetadata) => void;

  /** Transition the game to a new phase (investigation → resolved). */
  setPhase: (phase: GamePhase) => void;

  /** Store the result from POST /accuse for the resolution screen. */
  setAccusationResult: (result: AccuseResponse) => void;

  /**
   * Restore suspect states from a GET /session response (page reload).
   * Merges server-authoritative data without overwriting chat messages.
   */
  setSuspectStates: (states: Record<string, SuspectInteractionState>) => void;

  setCaseBrief: (brief: CaseBrief) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  setDifficulty: (difficulty: Difficulty) => void;
  setHint: (hint: string | null) => void;

  /** Reset entire store to initial state (new game / logout). */
  reset: () => void;
}

export type GameStore = GameState & GameActions;

// ── Initial state ─────────────────────────────────────────────────────────────

const initialState: GameState = {
  sessionId:       null,
  scenarioTitle:   "",
  setting:         "",
  phase:           "investigation",
  difficulty:      "medium",
  caseBrief:       null,
  suspects:        [],
  activeSuspectId: null,
  suspectStates:   {},
  messages:        {},
  evidence:        [],
  accusationResult: null,
  isLoading:       false,
  error:           null,
  hint:            null,
};

// ── Store ─────────────────────────────────────────────────────────────────────

export const useGameStore = create<GameStore>((set) => ({
  ...initialState,

  startGame: (response) =>
    set((state) => ({
      sessionId:       response.session_id,
      scenarioTitle:   response.scenario_title,
      setting:         response.setting,
      phase:           "investigation",
      difficulty:      state.difficulty,  // preserve difficulty set before startGame
      suspects:        response.suspects,
      activeSuspectId: response.suspects[0]?.id ?? null,
      // Pre-initialise empty message arrays and default suspect states
      messages: Object.fromEntries(response.suspects.map((s) => [s.id, []])),
      suspectStates: Object.fromEntries(
        response.suspects.map((s) => [
          s.id,
          {
            suspect_id:         s.id,
            questions_asked:    0,
            pressure_level:     0,
            has_been_questioned: false,
            message_count:      0,
          } satisfies SuspectInteractionState,
        ]),
      ),
      evidence:        [],
      accusationResult: null,
      isLoading:       false,
      error:           null,
      hint:            null,
      caseBrief:       response.case_brief ?? null,
    })),

  switchSuspect: (suspectId) =>
    set((state) => ({
      activeSuspectId: suspectId,
      messages: suspectId in state.messages
        ? state.messages
        : { ...state.messages, [suspectId]: [] },
    })),

  appendMessage: (suspectId, message) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [suspectId]: [...(state.messages[suspectId] ?? []), message],
      },
    })),

  appendToken: (suspectId, messageId, token) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [suspectId]: (state.messages[suspectId] ?? []).map((msg) =>
          msg.id === messageId
            ? { ...msg, content: msg.content + token }
            : msg,
        ),
      },
    })),

  finalizeMessage: (suspectId, messageId) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [suspectId]: (state.messages[suspectId] ?? []).map((msg) =>
          msg.id === messageId ? { ...msg, isStreaming: false } : msg,
        ),
      },
    })),

  removeMessage: (suspectId, messageId) =>
    set((state) => ({
      messages: {
        ...state.messages,
        [suspectId]: (state.messages[suspectId] ?? []).filter(
          (msg) => msg.id !== messageId,
        ),
      },
    })),

  applyMetadata: (suspectId, metadata) =>
    set((state) => {
      const current = state.suspectStates[suspectId] ?? {
        suspect_id:          suspectId,
        questions_asked:     0,
        pressure_level:      0,
        has_been_questioned: false,
        message_count:       0,
      };
      return {
        suspectStates: {
          ...state.suspectStates,
          [suspectId]: {
            ...current,
            pressure_level:     metadata.new_pressure_level,
            has_been_questioned: true,
          },
        },
        evidence: metadata.new_clues.length > 0
          ? [...state.evidence, ...metadata.new_clues]
          : state.evidence,
      };
    }),

  setPhase: (phase) => set({ phase }),

  setAccusationResult: (result) =>
    set({
      accusationResult: result,
      phase: "resolved",
    }),

  setSuspectStates: (states) =>
    set({ suspectStates: states }),

  setCaseBrief:  (caseBrief)  => set({ caseBrief }),
  setLoading:    (loading)    => set({ isLoading: loading }),
  setError:      (error)      => set({ error }),
  setDifficulty: (difficulty) => set({ difficulty }),
  setHint:       (hint)       => set({ hint }),
  reset:         ()           => set(initialState),
}));
