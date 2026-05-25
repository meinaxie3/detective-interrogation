/**
 * gameStore.test.ts — Unit tests for the Zustand game store.
 *
 * Each test grabs a fresh store instance via useGameStore.getState()
 * and resets it before/after so state never bleeds between tests.
 *
 * Phase 2 additions cover:
 *   - suspectStates / pressure tracking
 *   - applyMetadata (SSE done event)
 *   - setPhase / setAccusationResult
 *   - setSuspectStates (page-reload rehydration)
 *   - evidence accumulation
 */

import { describe, it, expect, beforeEach } from "vitest";
import { useGameStore } from "@/stores/gameStore";
import type {
  NewGameResponse,
  ChatMessage,
  ChatMetadata,
  AccuseResponse,
  SuspectInteractionState,
} from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

const MOCK_GAME: NewGameResponse = {
  session_id:     "test-session-123",
  scenario_title: "The Ashworth Manor Affair",
  setting:        "A rainy evening in 1920.",
  suspects: [
    { id: "butler", name: "James Beckett",  cover_story: "Was in the kitchen." },
    { id: "niece",  name: "Clara Ashworth", cover_story: "Was in her room."    },
  ],
  case_brief: {
    victim:         "Lord Ashworth",
    location:       "The study",
    time_of_death:  "11 PM",
    scenario_title: "The Ashworth Manor Affair",
    setting:        "A rainy evening in 1920.",
  },
};

function makeMsg(overrides: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id:         "msg-1",
    role:       "player",
    content:    "Hello",
    suspect_id: "butler",
    timestamp:  new Date(),
    ...overrides,
  };
}

function makeMetadata(overrides: Partial<ChatMetadata> = {}): ChatMetadata {
  return {
    consistency_passed: true,
    new_clues:          [],
    pressure_delta:     1,
    new_pressure_level: 1,
    new_evidence_found: false,
    ...overrides,
  };
}

const MOCK_ACCUSE_RESULT: AccuseResponse = {
  is_correct:           true,
  correct_culprit_id:   "butler",
  correct_motive:       "embezzlement cover-up",
  correct_method:       "arsenic in the wine",
  score:                80,
  resolution_narrative: "James Beckett is guilty.",
};

// ── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  useGameStore.getState().reset();
});

// ── Initial state ─────────────────────────────────────────────────────────────

describe("initial state", () => {
  it("has no session", () => {
    expect(useGameStore.getState().sessionId).toBeNull();
  });

  it("has no active suspect", () => {
    expect(useGameStore.getState().activeSuspectId).toBeNull();
  });

  it("is in investigation phase", () => {
    expect(useGameStore.getState().phase).toBe("investigation");
  });

  it("has empty messages", () => {
    expect(useGameStore.getState().messages).toEqual({});
  });

  it("is not loading", () => {
    expect(useGameStore.getState().isLoading).toBe(false);
  });

  it("has empty suspectStates", () => {
    expect(useGameStore.getState().suspectStates).toEqual({});
  });

  it("has empty evidence", () => {
    expect(useGameStore.getState().evidence).toEqual([]);
  });

  it("has no accusation result", () => {
    expect(useGameStore.getState().accusationResult).toBeNull();
  });
});

// ── startGame ─────────────────────────────────────────────────────────────────

describe("startGame()", () => {
  it("sets session_id", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().sessionId).toBe("test-session-123");
  });

  it("sets scenario_title", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().scenarioTitle).toBe("The Ashworth Manor Affair");
  });

  it("populates suspects list", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().suspects).toHaveLength(2);
  });

  it("sets first suspect as active", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().activeSuspectId).toBe("butler");
  });

  it("pre-initialises empty message arrays for all suspects", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    const msgs = useGameStore.getState().messages;
    expect(msgs["butler"]).toEqual([]);
    expect(msgs["niece"]).toEqual([]);
  });

  it("initialises suspectStates with pressure 0 for each suspect", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    const states = useGameStore.getState().suspectStates;
    expect(states["butler"].pressure_level).toBe(0);
    expect(states["niece"].pressure_level).toBe(0);
  });

  it("initialises suspectStates with has_been_questioned=false", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    const states = useGameStore.getState().suspectStates;
    expect(states["butler"].has_been_questioned).toBe(false);
  });

  it("clears evidence on new game", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    useGameStore.getState().applyMetadata("butler", makeMetadata({
      new_clues: [{
        clue_id: "c1", suspect_id: "butler",
        text: "kitchen", category: "location", turn: 1,
      }],
    }));
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().evidence).toEqual([]);
  });

  it("does not carry old messages from a previous game", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    useGameStore.getState().appendMessage("butler", makeMsg());
    useGameStore.getState().startGame(MOCK_GAME);
    expect(useGameStore.getState().messages["butler"]).toEqual([]);
  });
});

// ── switchSuspect ─────────────────────────────────────────────────────────────

describe("switchSuspect()", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("updates activeSuspectId", () => {
    useGameStore.getState().switchSuspect("niece");
    expect(useGameStore.getState().activeSuspectId).toBe("niece");
  });

  it("does not clear the previous suspect's messages", () => {
    useGameStore.getState().appendMessage("butler", makeMsg());
    useGameStore.getState().switchSuspect("niece");
    expect(useGameStore.getState().messages["butler"]).toHaveLength(1);
  });

  it("creates an empty entry for a suspect with no messages", () => {
    useGameStore.getState().reset();
    useGameStore.getState().switchSuspect("butler");
    expect(useGameStore.getState().messages["butler"]).toEqual([]);
  });
});

// ── appendMessage ─────────────────────────────────────────────────────────────

describe("appendMessage()", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("adds a message to the correct suspect", () => {
    const msg = makeMsg({ id: "m1", suspect_id: "butler" });
    useGameStore.getState().appendMessage("butler", msg);
    expect(useGameStore.getState().messages["butler"]).toHaveLength(1);
  });

  it("does not affect other suspects' messages", () => {
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "m1" }));
    expect(useGameStore.getState().messages["niece"]).toHaveLength(0);
  });

  it("preserves message order", () => {
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "m1", content: "first"  }));
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "m2", content: "second" }));
    const msgs = useGameStore.getState().messages["butler"];
    expect(msgs[0].content).toBe("first");
    expect(msgs[1].content).toBe("second");
  });
});

// ── appendToken / finalizeMessage ─────────────────────────────────────────────

describe("streaming: appendToken + finalizeMessage", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("appends tokens to the correct streaming message", () => {
    const placeholder = makeMsg({ id: "stream-1", content: "", isStreaming: true });
    useGameStore.getState().appendMessage("butler", placeholder);

    useGameStore.getState().appendToken("butler", "stream-1", "Hello");
    useGameStore.getState().appendToken("butler", "stream-1", " world");

    const msg = useGameStore.getState().messages["butler"].find((m) => m.id === "stream-1");
    expect(msg?.content).toBe("Hello world");
  });

  it("does not modify other messages when appending a token", () => {
    const other  = makeMsg({ id: "other-1", content: "unchanged" });
    const stream = makeMsg({ id: "stream-1", content: "", isStreaming: true });
    useGameStore.getState().appendMessage("butler", other);
    useGameStore.getState().appendMessage("butler", stream);

    useGameStore.getState().appendToken("butler", "stream-1", "X");

    const unchanged = useGameStore.getState().messages["butler"].find((m) => m.id === "other-1");
    expect(unchanged?.content).toBe("unchanged");
  });

  it("sets isStreaming=false after finalizeMessage", () => {
    const msg = makeMsg({ id: "s1", isStreaming: true });
    useGameStore.getState().appendMessage("butler", msg);
    useGameStore.getState().finalizeMessage("butler", "s1");

    const result = useGameStore.getState().messages["butler"].find((m) => m.id === "s1");
    expect(result?.isStreaming).toBe(false);
  });
});

// ── removeMessage ─────────────────────────────────────────────────────────────

describe("removeMessage()", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("removes the message with the given id", () => {
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "del-me" }));
    useGameStore.getState().removeMessage("butler", "del-me");
    const msgs = useGameStore.getState().messages["butler"];
    expect(msgs.find((m) => m.id === "del-me")).toBeUndefined();
  });

  it("leaves other messages intact", () => {
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "keep" }));
    useGameStore.getState().appendMessage("butler", makeMsg({ id: "del-me" }));
    useGameStore.getState().removeMessage("butler", "del-me");
    expect(useGameStore.getState().messages["butler"]).toHaveLength(1);
    expect(useGameStore.getState().messages["butler"][0].id).toBe("keep");
  });
});

// ── applyMetadata ─────────────────────────────────────────────────────────────

describe("applyMetadata()", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("updates the suspect's pressure_level to new_pressure_level", () => {
    useGameStore.getState().applyMetadata("butler", makeMetadata({ new_pressure_level: 3 }));
    expect(useGameStore.getState().suspectStates["butler"].pressure_level).toBe(3);
  });

  it("marks the suspect as has_been_questioned=true", () => {
    useGameStore.getState().applyMetadata("butler", makeMetadata());
    expect(useGameStore.getState().suspectStates["butler"].has_been_questioned).toBe(true);
  });

  it("does not affect other suspects' pressure", () => {
    useGameStore.getState().applyMetadata("butler", makeMetadata({ new_pressure_level: 5 }));
    expect(useGameStore.getState().suspectStates["niece"].pressure_level).toBe(0);
  });

  it("appends new clues to the evidence list", () => {
    const clue = {
      clue_id: "c1", suspect_id: "butler",
      text: "kitchen", category: "location" as const, turn: 1,
    };
    useGameStore.getState().applyMetadata("butler", makeMetadata({
      new_clues: [clue], new_evidence_found: true,
    }));
    expect(useGameStore.getState().evidence).toHaveLength(1);
    expect(useGameStore.getState().evidence[0].clue_id).toBe("c1");
  });

  it("does not modify evidence when new_clues is empty", () => {
    useGameStore.getState().applyMetadata("butler", makeMetadata({ new_clues: [] }));
    expect(useGameStore.getState().evidence).toHaveLength(0);
  });

  it("accumulates clues across multiple calls", () => {
    const clue1 = { clue_id: "c1", suspect_id: "butler", text: "kitchen", category: "location" as const, turn: 1 };
    const clue2 = { clue_id: "c2", suspect_id: "niece",  text: "hallway", category: "location" as const, turn: 2 };
    useGameStore.getState().applyMetadata("butler", makeMetadata({ new_clues: [clue1] }));
    useGameStore.getState().applyMetadata("niece",  makeMetadata({ new_clues: [clue2] }));
    expect(useGameStore.getState().evidence).toHaveLength(2);
  });

  it("works for an unknown suspect (creates default state)", () => {
    useGameStore.getState().reset();
    useGameStore.getState().applyMetadata("doctor", makeMetadata({ new_pressure_level: 2 }));
    expect(useGameStore.getState().suspectStates["doctor"].pressure_level).toBe(2);
  });
});

// ── setPhase ──────────────────────────────────────────────────────────────────

describe("setPhase()", () => {
  it("transitions phase to resolved", () => {
    useGameStore.getState().setPhase("resolved");
    expect(useGameStore.getState().phase).toBe("resolved");
  });

  it("transitions phase back to investigation", () => {
    useGameStore.getState().setPhase("resolved");
    useGameStore.getState().setPhase("investigation");
    expect(useGameStore.getState().phase).toBe("investigation");
  });
});

// ── setAccusationResult ───────────────────────────────────────────────────────

describe("setAccusationResult()", () => {
  it("stores the accusation result", () => {
    useGameStore.getState().setAccusationResult(MOCK_ACCUSE_RESULT);
    expect(useGameStore.getState().accusationResult).toEqual(MOCK_ACCUSE_RESULT);
  });

  it("transitions phase to resolved", () => {
    useGameStore.getState().setAccusationResult(MOCK_ACCUSE_RESULT);
    expect(useGameStore.getState().phase).toBe("resolved");
  });

  it("stores is_correct from the result", () => {
    useGameStore.getState().setAccusationResult(MOCK_ACCUSE_RESULT);
    expect(useGameStore.getState().accusationResult?.is_correct).toBe(true);
  });

  it("stores an incorrect result correctly", () => {
    const wrong = { ...MOCK_ACCUSE_RESULT, is_correct: false };
    useGameStore.getState().setAccusationResult(wrong);
    expect(useGameStore.getState().accusationResult?.is_correct).toBe(false);
  });
});

// ── setSuspectStates ──────────────────────────────────────────────────────────

describe("setSuspectStates()", () => {
  beforeEach(() => {
    useGameStore.getState().startGame(MOCK_GAME);
  });

  it("overwrites the entire suspectStates map", () => {
    const restored: Record<string, SuspectInteractionState> = {
      butler: {
        suspect_id: "butler", questions_asked: 5,
        pressure_level: 4, has_been_questioned: true, message_count: 10,
      },
      niece: {
        suspect_id: "niece", questions_asked: 2,
        pressure_level: 2, has_been_questioned: true, message_count: 4,
      },
    };
    useGameStore.getState().setSuspectStates(restored);
    expect(useGameStore.getState().suspectStates["butler"].pressure_level).toBe(4);
    expect(useGameStore.getState().suspectStates["niece"].pressure_level).toBe(2);
  });

  it("does not touch the messages map", () => {
    useGameStore.getState().appendMessage("butler", makeMsg());
    useGameStore.getState().setSuspectStates({
      butler: {
        suspect_id: "butler", questions_asked: 3,
        pressure_level: 2, has_been_questioned: true, message_count: 6,
      },
    });
    expect(useGameStore.getState().messages["butler"]).toHaveLength(1);
  });
});

// ── reset ─────────────────────────────────────────────────────────────────────

describe("reset()", () => {
  it("clears all state back to initial", () => {
    useGameStore.getState().startGame(MOCK_GAME);
    useGameStore.getState().appendMessage("butler", makeMsg());
    useGameStore.getState().applyMetadata("butler", makeMetadata({ new_pressure_level: 3 }));
    useGameStore.getState().setAccusationResult(MOCK_ACCUSE_RESULT);
    useGameStore.getState().reset();

    const state = useGameStore.getState();
    expect(state.sessionId).toBeNull();
    expect(state.suspects).toHaveLength(0);
    expect(state.messages).toEqual({});
    expect(state.suspectStates).toEqual({});
    expect(state.evidence).toEqual([]);
    expect(state.accusationResult).toBeNull();
    expect(state.phase).toBe("investigation");
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });
});
