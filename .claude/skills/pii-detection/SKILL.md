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

---

# The missed-PII finder (Sam's differentiator)

Sam's hard half is the PII the tool LEFT VISIBLE — false negatives. The original detector
already missed these, so you cannot reuse it; you run a SECOND, separate service over the
un-redacted text. Keep it as its own clearly-named module (`MissedPiiFinder`) distinct from
the original `Detector` — that separation is itself good engineering the judges will notice.

Input: original text + the set of spans the tool already redacted.
Output: candidate spans over the still-visible text, each with a `lens` and a `reason`.

## Three complementary lenses (precision descending)
1. **Format pass — regex (high precision, deterministic, free).**
   Match shapes in visible text: phone, email, SSN/national-id, card/account, IP, URL,
   policy/case numbers. This directly catches the missed phone number from the brief. Fast and
   needs no model — run it always. Example phone matcher: digit groups with optional spaces /
   dashes / parens, length-validated, anchored to word boundaries; then verify it isn't already
   inside a redacted span before flagging.

2. **Entity-consistency pass — propagate confident redactions (high precision, no model).**
   THE differentiator. For every span the tool redacted with high confidence, take its value
   and its meaningful sub-tokens (e.g. "Margaret Holloway" → also "Margaret", "Holloway") and
   search for any UN-redacted occurrence elsewhere. If the tool was sure enough to hide it once,
   the same value left visible is almost certainly a miss. Catches duplicate phone numbers and
   half-redacted names with near-zero false alarms. Cheap, deterministic, and impressive.

3. **Semantic pass — LLM/NER (lower precision, optional).**
   For novel PII with no prior redaction to anchor on — e.g. a doctor's name beside a medical
   condition. Prompt the LLM: "Here is the text WITH the tool's redactions already applied. What
   identifying information did it MISS?" Return candidates as REVIEW only — never auto-redact —
   because precision is lower. Use it to catch what lenses 1–2 structurally cannot.

## Calibration (avoid crying wolf)
Tag each candidate with its lens so the UX can weight it: format + consistency → strong,
pre-suggestable; semantic → soft "review". Always attach a human-readable `reason`
("matches phone format", "you redacted this name elsewhere", "name adjacent to a medical
term"). Over-flagging makes Sam tune out the warnings and miss the real one — precision is the
product here, not recall-at-any-cost.

## Consistency conflict (a first-class signal)
When lens 2 fires, it's not just a missed span — it's a *conflict*: "redacted here, visible
there." Surface it as its own flag type with both locations, because it's the most convincing,
most demoable catch ("the tool was inconsistent with itself").

## Don't double-flag
Always check a candidate isn't already covered by an existing redaction or another candidate
before surfacing it. Clamp to bounds, normalize, sort — same hygiene as the primary detector.

## Test against the fixture
`fixtures/tool-suggestions.json` is what the flawed detector returns (false positives in,
missed PII out). `fixtures/expected-corrections.json` is the oracle: the finder must recover
every entry in `add_missed_pii` with the right lens, and the UX must flag every
`remove_false_positives` item as a likely over-redaction. Make this a test — it doubles as
proof of the discovery for the writeup.
