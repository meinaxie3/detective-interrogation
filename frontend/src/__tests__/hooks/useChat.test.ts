/**
 * useChat.test.ts — Unit tests for the chat streaming hook.
 *
 * Strategy: mock @/lib/api at the module level so sendChatMessage
 * returns a crafted Response with a fake ReadableStream body.
 * We then test the store mutations that result.
 *
 * No MSW needed — vi.mock gives us full control over fetch behaviour.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useChat } from "@/hooks/useChat";
import { useGameStore } from "@/stores/gameStore";
import type { NewGameResponse } from "@/lib/types";

// ── Module mock ───────────────────────────────────────────────────────────────

vi.mock("@/lib/api", () => ({
  sendChatMessage: vi.fn(),
  ApiError: class ApiError extends Error {
    constructor(public status: number, message: string) {
      super(message);
      this.name = "ApiError";
    }
  },
}));

// Import the mocked version after vi.mock is hoisted
import { sendChatMessage } from "@/lib/api";
const mockSendChatMessage = vi.mocked(sendChatMessage);

// ── SSE stream helpers ────────────────────────────────────────────────────────

function encodeSSE(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line + "\n"));
      }
      controller.close();
    },
  });
}

function sseToken(content: string) {
  return `data: ${JSON.stringify({ type: "token", content })}`;
}

function sseDone(pressureLevel = 1) {
  return `data: ${JSON.stringify({
    type: "done",
    metadata: {
      consistency_passed: true,
      new_clues:          [],
      pressure_delta:     1,
      new_pressure_level: pressureLevel,
      new_evidence_found: false,
    },
  })}`;
}

function sseError(message: string) {
  return `data: ${JSON.stringify({ type: "error", message })}`;
}

function makeResponse(lines: string[]): Response {
  return new Response(encodeSSE(lines), { status: 200 });
}

// ── Store setup ───────────────────────────────────────────────────────────────

const MOCK_GAME: NewGameResponse = {
  session_id:     "sess-test",
  scenario_title: "Test Case",
  setting:        "",
  suspects: [
    { id: "butler", name: "James Beckett", cover_story: "In the kitchen." },
    { id: "niece",  name: "Clara",         cover_story: "In her room."    },
  ],
  case_brief: {
    victim:         "Lord Ashworth",
    location:       "The study",
    time_of_death:  "11 PM",
    scenario_title: "Test Case",
    setting:        "",
  },
};

beforeEach(() => {
  useGameStore.getState().reset();
  useGameStore.getState().startGame(MOCK_GAME);
  vi.clearAllMocks();
});

// ── Sending a message ─────────────────────────────────────────────────────────

describe("useChat — sending a message", () => {
  it("appends the player message to the store before the stream starts", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("Hello"), sseDone()])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Where were you?");
    });

    const msgs = useGameStore.getState().messages["butler"];
    const playerMsg = msgs.find((m) => m.role === "player");
    expect(playerMsg?.content).toBe("Where were you?");
  });

  it("calls sendChatMessage with correct session_id, suspect_id, message", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseDone()])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello");
    });

    expect(mockSendChatMessage).toHaveBeenCalledWith("sess-test", "butler", "Hello");
  });

  it("sets isLoading=false after the stream ends", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("OK"), sseDone()])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hi");
    });

    expect(useGameStore.getState().isLoading).toBe(false);
  });

  it("does nothing when text is empty", async () => {
    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("   ");
    });

    expect(mockSendChatMessage).not.toHaveBeenCalled();
  });

  it("does nothing when sessionId is null", async () => {
    useGameStore.getState().reset(); // clears sessionId

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello");
    });

    expect(mockSendChatMessage).not.toHaveBeenCalled();
  });
});

// ── Streaming tokens ──────────────────────────────────────────────────────────

describe("useChat — streaming tokens", () => {
  it("builds up the character response token by token", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("I was"), sseToken(" in"), sseToken(" the kitchen."), sseDone()])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Where were you?");
    });

    const msgs = useGameStore.getState().messages["butler"];
    const charMsg = msgs.find((m) => m.role === "character");
    expect(charMsg?.content).toBe("I was in the kitchen.");
  });

  it("marks the character message isStreaming=false after stream ends", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("Done."), sseDone()])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Tell me.");
    });

    const msgs = useGameStore.getState().messages["butler"];
    const charMsg = msgs.find((m) => m.role === "character");
    expect(charMsg?.isStreaming).toBe(false);
  });

  it("adds a streaming placeholder before tokens arrive", async () => {
    // Use a slow-resolving mock to check intermediate state
    let resolveStream!: () => void;
    const streamPromise = new Promise<void>((r) => { resolveStream = r; });

    mockSendChatMessage.mockImplementation(async () => {
      await streamPromise;
      return makeResponse([sseDone()]);
    });

    const { result } = renderHook(() => useChat());

    // Start the send (don't await yet)
    let sendDone = false;
    act(() => {
      result.current.sendMessage("Hello").then(() => { sendDone = true; });
    });

    // At this point the player message should be in the store
    const msgs = useGameStore.getState().messages["butler"];
    expect(msgs.some((m) => m.role === "player")).toBe(true);

    // Let the stream finish
    resolveStream();
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    expect(sendDone).toBe(true);
  });
});

// ── Metadata event ────────────────────────────────────────────────────────────

describe("useChat — metadata event", () => {
  it("calls applyMetadata with the correct pressure level", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("Response."), sseDone(3)])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Push harder.");
    });

    expect(
      useGameStore.getState().suspectStates["butler"].pressure_level
    ).toBe(3);
  });

  it("marks the suspect as has_been_questioned after metadata", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("Yes."), sseDone(1)])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(
      useGameStore.getState().suspectStates["butler"].has_been_questioned
    ).toBe(true);
  });

  it("adds clues to evidence when new_clues is non-empty", async () => {
    const clue = {
      clue_id: "clue-1", suspect_id: "butler",
      text: "kitchen", category: "location", turn: 1,
    };
    const doneWithClue = `data: ${JSON.stringify({
      type: "done",
      metadata: {
        consistency_passed: true,
        new_clues:          [clue],
        pressure_delta:     1,
        new_pressure_level: 1,
        new_evidence_found: true,
      },
    })}`;

    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("I saw it."), doneWithClue])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("What did you see?");
    });

    expect(useGameStore.getState().evidence).toHaveLength(1);
    expect(useGameStore.getState().evidence[0].clue_id).toBe("clue-1");
  });

  it("does not add to evidence when new_clues is empty", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("Nothing."), sseDone(1)])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Anything?");
    });

    expect(useGameStore.getState().evidence).toHaveLength(0);
  });

  it("does not include metadata in the chat message text", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseToken("I was there."), sseDone(2)])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Where?");
    });

    const msgs = useGameStore.getState().messages["butler"];
    const charMsg = msgs.find((m) => m.role === "character");
    expect(charMsg?.content).toBe("I was there.");
    expect(charMsg?.content).not.toContain("pressure");
  });
});

// ── Error handling ────────────────────────────────────────────────────────────

describe("useChat — error handling", () => {
  it("sets error state on SSE error event", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseError("Something broke.")])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(useGameStore.getState().error).toBeTruthy();
  });

  it("removes the streaming placeholder on error", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseError("Oops.")])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    const msgs = useGameStore.getState().messages["butler"];
    // Streaming placeholder should be removed; no empty character messages
    const emptyCharMsg = msgs.find((m) => m.role === "character" && m.content === "");
    expect(emptyCharMsg).toBeUndefined();
  });

  it("sets isLoading=false after an error", async () => {
    mockSendChatMessage.mockResolvedValue(
      makeResponse([sseError("Error.")])
    );

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(useGameStore.getState().isLoading).toBe(false);
  });

  it("sets error on network failure (sendChatMessage throws)", async () => {
    mockSendChatMessage.mockRejectedValue(new Error("Network failure"));

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(useGameStore.getState().error).toContain("Network failure");
  });

  it("shows descriptive message for 404 ApiError", async () => {
    const { ApiError } = await import("@/lib/api");
    mockSendChatMessage.mockRejectedValue(new ApiError(404, "not found"));

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(useGameStore.getState().error).toContain("expired");
  });

  it("shows descriptive message for 409 ApiError", async () => {
    const { ApiError } = await import("@/lib/api");
    mockSendChatMessage.mockRejectedValue(new ApiError(409, "resolved"));

    const { result } = renderHook(() => useChat());
    await act(async () => {
      await result.current.sendMessage("Hello.");
    });

    expect(useGameStore.getState().error).toContain("closed");
  });
});
