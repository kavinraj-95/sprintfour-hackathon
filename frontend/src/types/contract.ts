// The shared contract — mirror of backend/models/contract.py.
//
// This is the SAME data model the server uses, expressed in TypeScript. If a
// type changes on one side, change it on the other; the two are kept in
// lockstep on purpose so the wire format is impossible to drift.
//
// ============================ THE OFFSET RULE ============================
// A Span addresses a slice of `SessionState.originalText` by [start, end),
// where start/end are CODEPOINT indices and end is exclusive. The invariant,
// true for every span:
//
//     span.text === [...originalText].slice(span.start, span.end).join("")
//
// We pin offsets to codepoints (not UTF-16 code units) because the backend
// indexes Python `str` by codepoint. For text in the Basic Multilingual Plane
// this equals normal JS string indexing; for astral characters (emoji, some
// CJK) use `Array.from(text)` / spread to index by codepoint. The backend is
// the authority and asserts the rule wherever a span is created.
// ========================================================================

// Kept deliberately small — mirrors PiiType on the backend.
export type PiiType =
  | "PERSON"
  | "ORG"
  | "EMAIL"
  | "PHONE"
  | "ADDRESS"
  | "ID_NUMBER"
  | "OTHER";

// Where a span came from — the producing detection layer, or "manual".
export type SpanSource = "regex" | "dictionary" | "ner" | "llm" | "manual";

// How a confirmed span is rendered in the exported document.
export type OutputMode = "REDACT" | "ANONYMIZE";

export interface Span {
  id: string;
  start: number; // codepoint index into originalText, inclusive
  end: number; // codepoint index into originalText, exclusive
  text: string; // exactly originalText[start:end]
  type: PiiType;
  confidence: number; // 0–1
  source: SpanSource;
  reason: string; // human-readable "why this span?"
}

export interface SessionState {
  session_id: string;
  original_text: string;
  spans: Span[];
  output_mode: OutputMode;
}

// Uniform error envelope returned by every failing endpoint.
export interface ErrorResponse {
  error: string;
  detail: string | null;
}
