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
  // Canonical form (digits-only for phones, lowercased for emails), recorded so
  // a later merge step can link duplicate occurrences. Null/absent when N/A.
  normalized_value?: string | null;
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

// ============================ REVIEW SURFACE ============================
// DTOs for Sam's correction experience — a 1:1 mirror of backend/models/api.py.
// The queue is the product; SessionState above is the lower-level seam.
//
// `tier` uses ONE vocabulary shared with the merge step:
//   1 = high risk   (structured agreement, or any linked-duplicate) — shown first
//   2 = low confidence (likely false positives — easy to confirm or flip)
//   3 = soft review (llm-only catches; dismissible without a forced binary)
// ========================================================================

export type ReviewTier = 1 | 2 | 3;
export type ItemStatus = "pending" | "accepted" | "dismissed";
export type LayerState = "ok" | "skipped" | "error";
export type ActionType = "accept" | "dismiss" | "add_missed" | "undo";

// Honest report of one detection layer, for the "what ran" panel.
export interface LayerStatus {
  name: string;
  status: LayerState;
  count: number;
  detail: string;
}

// One other visible spot the same value appears (codepoint offsets).
export interface OccurrenceRef {
  start: number;
  end: number;
}

// One row of the risk-ranked queue: a finding + the reviewer's decision
// + one-glance sentence context, so Sam rarely needs to open the document.
export interface ReviewItem {
  id: string;
  start: number;
  end: number;
  text: string;
  type: PiiType;
  confidence: number;
  sources: string[];
  reason: string;
  normalized_value: string | null;
  tier: ReviewTier;
  linked: OccurrenceRef[]; // other visible occurrences of the same value
  linked_count: number;
  status: ItemStatus;
  sentence: string;
}

export interface ReviewCounts {
  tier1: number;
  tier2: number;
  tier3: number;
  accepted: number;
  dismissed: number;
  pending: number;
  // Tier-1 items still pending. > 0 gates export.
  unresolved_high_risk: number;
}

// The whole correction surface in one payload.
export interface ReviewState {
  session_id: string;
  original_text: string;
  output_mode: OutputMode;
  layers: LayerStatus[];
  queue: ReviewItem[];
  counts: ReviewCounts;
}

// One row of the export key. Carries NO raw PII — safe to share.
export interface LegendEntry {
  token: string;
  type: PiiType;
  occurrences: number;
}

// /preview response: the live REDACT/ANONYMIZE render, no re-detection.
export interface PreviewResult {
  output_text: string;
  legend: LegendEntry[];
}

// /export response. `gated=true` means nothing rendered — the export was held
// back and `unresolved` lists the high-risk items still open.
export interface ExportResult {
  gated: boolean;
  output_text: string | null;
  legend: LegendEntry[];
  unresolved: ReviewItem[];
}

// A single reversible gesture sent to /action.
export interface ActionRequest {
  type: ActionType;
  target_id?: string;
  start?: number;
  end?: number;
  pii_type?: PiiType;
}
