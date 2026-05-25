/**
 * api.test.ts — Unit tests for the API client functions.
 *
 * The API client (src/lib/api.ts) is a thin wrapper around fetch.
 * These tests verify that it hits the right endpoints with the right
 * payload shape — not what the server returns.
 *
 * Uses MSW to intercept calls. No real network.
 *
 * TODO (Phase 1): implement api.ts, then remove skip markers.
 */

import { describe, it, expect } from "vitest";

// TODO: import { createGame, sendMessage, accuse, getSession } from "@/lib/api"

describe("api.createGame()", () => {
  it.todo("sends POST to /new-game");
  it.todo("sends scenario_id in the request body");
  it.todo("defaults to 'manor_1920' when no scenario_id provided");
  it.todo("returns a NewGameResponse with session_id and suspects");
});

describe("api.sendMessage()", () => {
  it.todo("sends POST to /chat");
  it.todo("includes session_id, suspect_id, and message in body");
  it.todo("returns a ReadableStream for SSE parsing");
  it.todo("throws an ApiError on non-200 status");
});

describe("api.accuse()", () => {
  it.todo("sends POST to /accuse");
  it.todo("includes session_id, suspect_id, motive, method");
  it.todo("returns an AccuseResponse with is_correct field");
});

describe("api.getSession()", () => {
  it.todo("sends GET to /session/{session_id}");
  it.todo("returns a GameSession object");
  it.todo("throws 404 error for unknown session_id");
});
