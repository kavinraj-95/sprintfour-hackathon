// Typed API client — the single place the frontend talks to the backend.
//
// Every call returns the contract types from ../types/contract, and every
// failure throws an ApiError carrying the server's typed ErrorResponse, so
// callers never have to parse error shapes themselves.

import type {
  ErrorResponse,
  OutputMode,
  SessionState,
} from "../types/contract";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    detail: string | null,
  ) {
    super(detail ?? code);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    // The backend always returns the ErrorResponse envelope, never a bare 500.
    let body: ErrorResponse = { error: "unknown_error", detail: res.statusText };
    try {
      body = (await res.json()) as ErrorResponse;
    } catch {
      // fall through with the default envelope
    }
    throw new ApiError(res.status, body.error, body.detail);
  }
  return (await res.json()) as T;
}

export interface Health {
  status: string;
  detector: string;
}

export const api = {
  health: () => request<Health>("/api/health"),

  initSession: (text: string, outputMode: OutputMode = "REDACT") =>
    request<SessionState>("/api/session/init", {
      method: "POST",
      body: JSON.stringify({ text, output_mode: outputMode }),
    }),

  getSession: (sessionId: string) =>
    request<SessionState>(`/api/session/${sessionId}`),
};
