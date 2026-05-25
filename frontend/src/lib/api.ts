/**
 * api.ts — Typed fetch wrappers for every backend endpoint.
 *
 * All calls go through Next.js's /api rewrite (configured in next.config.ts),
 * which proxies to the FastAPI backend. This avoids CORS issues in dev and
 * lets us point to a different backend URL in production via NEXT_PUBLIC_API_URL.
 *
 * Convention: functions throw an ApiError with a human-readable message on
 * any non-2xx response. The caller decides how to surface it.
 */

import type {
  NewGameResponse,
  SessionStateResponse,
  AccuseRequest,
  AccuseResponse,
  GameRecord,
  HintResponse,
  Difficulty,
} from "./types";

// Use the rewrite prefix so Next.js proxies to the backend
const API = "/api";

// ── Errors ───────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (res.ok) return res.json() as Promise<T>;
  let detail = `HTTP ${res.status}`;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
  } catch {
    // ignore parse error — use the default
  }
  throw new ApiError(res.status, detail);
}

// ── Game lifecycle ────────────────────────────────────────────────────────────

export async function createGame(
  scenarioId  = "manor_1920",
  difficulty: Difficulty = "medium",
): Promise<NewGameResponse> {
  const res = await fetch(`${API}/new-game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId, difficulty }),
  });
  return handleResponse<NewGameResponse>(res);
}

export async function getSession(
  sessionId: string,
): Promise<SessionStateResponse> {
  const res = await fetch(`${API}/session/${sessionId}`);
  return handleResponse<SessionStateResponse>(res);
}

// ── Chat (streaming) ──────────────────────────────────────────────────────────

/**
 * Send a chat message and return the raw Response for SSE parsing.
 * The caller is responsible for reading response.body as a ReadableStream.
 * Throws ApiError on non-200 status before the stream starts.
 */
export async function sendChatMessage(
  sessionId: string,
  suspectId: string,
  message: string,
): Promise<Response> {
  const res = await fetch(`${API}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      suspect_id: suspectId,
      message,
    }),
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore
    }
    throw new ApiError(res.status, detail);
  }
  return res;
}

// ── History ───────────────────────────────────────────────────────────────────

export async function getHistory(): Promise<GameRecord[]> {
  const res = await fetch(`${API}/history`);
  return handleResponse<GameRecord[]>(res);
}

// ── Hint ──────────────────────────────────────────────────────────────────────

export async function requestHint(sessionId: string): Promise<HintResponse> {
  const res = await fetch(`${API}/hint`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return handleResponse<HintResponse>(res);
}

// ── Accusation ────────────────────────────────────────────────────────────────

export async function submitAccusation(
  request: AccuseRequest,
): Promise<AccuseResponse> {
  const res = await fetch(`${API}/accuse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return handleResponse<AccuseResponse>(res);
}
