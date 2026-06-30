---
name: pii-detection
description: >
  How to implement the PII detection layer for the Conseal hackathon: the span data model
  with character offsets, the cloud-LLM prompt that returns spans + types + confidence +
  reason, the mock-backend shape, normalization of messy/overlapping spans, and the single
  interface that makes the LLM and mock paths interchangeable. Use when building or wiring
  detection.
---

# PII Detection — implementation patterns

Detection is a means, not the point. Goal: correct, deterministic-when-mocked, and behind
ONE interface so the UX never depends on which path is active.

## The span model (the contract everyone shares)
A detection is character-offset based, into the ORIGINAL document text:

```
Span {
  id: string            // stable, e.g. "span_3"
  start: int            // inclusive offset into original text
  end: int              // exclusive offset
  text: string          // original.slice(start, end) — store for convenience/verification
  type: string          // PERSON | EMAIL | PHONE | ADDRESS | SSN | ... (see conseal-domain)
  confidence: float     // 0.0–1.0
  reason?: string       // one line — powers the "why this?" explanation
}
```

Offsets (not just text) are mandatory: the same string can appear twice and be redacted
independently, and overlaps are only detectable with positions. Keep offset semantics
consistent between backend and frontend (decide codepoints vs UTF-16 once and stick to it).

## One interface, two implementations
```
interface Detector { detect(documentText: string): Promise<Span[]> }
```
- `MockDetector` — returns a fixed, realistic list for the sample document(s). Always works
  offline, no API key. Spread confidences (some 0.99, some ~0.55) and include a couple of
  overlapping/duplicate spans so the UX has real messiness to handle. For the "mistakes"
  problem, deliberately seed a false positive and leave a real phone number/name OUT of the
  list (the missed PII Sam must catch).
- `LLMDetector` — calls a cloud LLM with the user's own key, server-side only.
A single config flag (`DETECTOR=mock|llm`) selects one. Nothing downstream knows which.

## Cloud-LLM prompt pattern
System: "You are a PII detection engine. Find every span of personally identifying
information in the user's document. Return ONLY JSON, no prose, no markdown fences."
Ask for an array of objects with `start`, `end`, `text`, `type`, `confidence` (calibrated
0–1), and a short `reason`. Constraints to include in the prompt:
- Offsets must index the exact text provided; `text` must equal the substring at start..end.
- Use the fixed type vocabulary; one type per span.
- Prefer recall but mark uncertain spans with lower confidence rather than omitting them.
Then validate the JSON yourself — the model WILL occasionally drift.

## Normalize before returning (both paths)
LLM and even hand-written mock output get messy. Always:
- Drop spans whose offsets fall outside the document, or where `text !== original[start:end]`
  (re-anchor by searching for `text` if you can, else discard and log).
- Clamp to bounds; ensure `start < end`.
- De-duplicate identical spans; for overlaps keep the higher-confidence / more-specific one
  OR keep both and let the UX show the overlap — decide per problem and document it.
- Sort by `start` for stable rendering.
Return clean spans so the frontend/redaction engine never has to defend against garbage.

## Failure handling
- LLM call fails / times out / returns non-JSON → return a typed error, never crash. The UX
  must degrade (show "detection unavailable", offer retry, fall back to mock if configured).
- Never send the API key or the raw document to the client. Detection runs server-side.

## Make it testable
Mock makes the whole pipeline deterministic. Add fixtures (sample doc + expected spans) and
one test asserting `detect()` returns normalized, in-bounds spans. This protects the UX from
silent detection regressions and is the kind of test the reviewer wants to see.
