/**
 * useChat.ts — Hook that drives the SSE streaming chat loop.
 *
 * Flow on sendMessage(text):
 *   1. Immediately append the player's message to the store
 *   2. Add a placeholder character message with isStreaming=true
 *   3. POST to /api/chat and read the SSE stream
 *   4. On each "token" event: call appendToken → the placeholder grows live
 *   5. On "done": call finalizeMessage + applyMetadata (pressure/clues update)
 *   6. On "error" or network failure: remove placeholder, set error state
 */

"use client";

import { useGameStore } from "@/stores/gameStore";
import { sendChatMessage, ApiError } from "@/lib/api";
import type { ChatMessage, SSEEvent } from "@/lib/types";

// ── SSE parsing helper ────────────────────────────────────────────────────────

function parseSSELine(line: string): SSEEvent | null {
  if (!line.startsWith("data: ")) return null;
  try {
    return JSON.parse(line.slice(6)) as SSEEvent;
  } catch {
    return null;
  }
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useChat() {
  const {
    sessionId,
    activeSuspectId,
    appendMessage,
    appendToken,
    finalizeMessage,
    removeMessage,
    applyMetadata,
    setLoading,
    setError,
  } = useGameStore();

  const sendMessage = async (text: string): Promise<void> => {
    const trimmed = text.trim();
    if (!trimmed || !sessionId || !activeSuspectId) return;

    setLoading(true);
    setError(null);

    // 1. Add player message immediately so the UI feels responsive
    const playerMsg: ChatMessage = {
      id:         crypto.randomUUID(),
      role:       "player",
      content:    trimmed,
      suspect_id: activeSuspectId,
      timestamp:  new Date(),
    };
    appendMessage(activeSuspectId, playerMsg);

    // 2. Add an empty streaming placeholder for the character's response
    const responseId = crypto.randomUUID();
    const placeholder: ChatMessage = {
      id:          responseId,
      role:        "character",
      content:     "",
      suspect_id:  activeSuspectId,
      timestamp:   new Date(),
      isStreaming: true,
    };
    appendMessage(activeSuspectId, placeholder);

    try {
      // 3. Start the SSE stream
      const response = await sendChatMessage(sessionId, activeSuspectId, trimmed);

      const reader = response.body?.getReader();
      if (!reader) throw new Error("No response body from server");

      const decoder = new TextDecoder();
      let buffer = "";

      // 4. Read stream chunk by chunk
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by double newlines; split on single newlines
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? ""; // Keep incomplete last line in buffer

        for (const line of lines) {
          const event = parseSSELine(line);
          if (!event) continue;

          if (event.type === "token") {
            appendToken(activeSuspectId, responseId, event.content);
          } else if (event.type === "done") {
            finalizeMessage(activeSuspectId, responseId);
            // Phase 2: update pressure level and evidence board
            if (event.metadata) {
              applyMetadata(activeSuspectId, event.metadata);
            }
          } else if (event.type === "error") {
            throw new Error(event.message);
          }
        }
      }

      // Finalize in case the stream ended without a "done" event
      finalizeMessage(activeSuspectId, responseId);
    } catch (err) {
      // Remove the empty placeholder so the UI doesn't show a blank bubble
      removeMessage(activeSuspectId, responseId);

      const message =
        err instanceof ApiError
          ? err.status === 404
            ? "Session not found. Your game may have expired."
            : err.status === 409
              ? "This investigation is already closed."
              : err.message
          : err instanceof Error
            ? err.message
            : "Something went wrong. Please try again.";

      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return { sendMessage };
}
