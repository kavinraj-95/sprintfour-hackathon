---
name: pii-contract
description: The shared data contract for Conseal — span shape, PII types, the codepoint offset rule, and the merge-step precedence table and risk tiers. Use whenever a span, type, offset, or the merge ranking is involved.
---

# PII Contract

One data shape, defined once, mirrored on backend (Pydantic) and frontend (TypeScript). Backend and frontend must never disagree about it.

## Types (keep exactly this small)
- `PiiType`: `PERSON, ORG, EMAIL, PHONE, ADDRESS, ID_NUMBER, OTHER`. Do not add values speculatively.
- `Span { id, start, end, text, type, confidence (0..1), source ("regex"|"dictionary"|"ner"|"llm"|"manual"), reason, normalized_value? }`
- `OutputMode`: `REDACT, ANONYMIZE`
- `SessionState { session_id, original_text, spans[], output_mode }`

## The offset rule (mandatory everywhere)
Offsets are **codepoint indices** into `original_text`. Every site that creates a Span must assert:

    assert span.text == original_text[span.start:span.end]

Frontend slicing uses `Array.from(text)` to stay codepoint-safe. If this assertion ever fails, the span is wrong — fix the anchoring, do not loosen the assertion.

## normalized_value
Regex records a normalized form (digits-only for phones, lowercased for emails) so the merge step can link duplicate occurrences. Names are normalized by casefold when compared.

## Merge precedence (the differentiation step)
All candidate spans go into one pure function; one ranked list comes out.
1. `regex` and `dictionary` are near-certain — they win ties outright.
2. `ner` vs `llm` disagreement on the same span -> the `llm` decision breaks the tie (it had the surrounding sentence as context).
3. `llm`-only catch with no structural backup -> keep it, but lower its severity.
4. Coalesce overlapping spans: union the `source` tags, keep the highest confidence, merge the reasons.
5. Link duplicates: the same `normalized_value` at multiple visible spots is tied together (record the linked occurrence offsets) so the UI can fix all at once.
6. Anything inside a dictionary ALLOWLIST range is suppressed and must not appear in the final list.

## Risk tiers (drive BOTH the merge output ordering and the UI queue — one vocabulary, not two)
- **Tier 1 — high risk:** sensitive PII with structural agreement, or any linked-duplicate. Shown first.
- **Tier 2 — low confidence:** flagged but uncertain (e.g. low-confidence redactions, possible false positives). Easy to confirm or flip.
- **Tier 3 — soft review:** `llm`-only catches with no structural backup. Dismissible without a forced binary.
