---
name: redaction-vs-anonymization
description: The precise distinction between redaction (remove) and anonymization (replace), the mechanism for each, the user-facing toggle, and the raster pixel-redaction warning. Use at the output/export stage.
---

# Redaction vs Anonymization

These are two genuinely different operations. The user chooses between them via `OutputMode`. Never collapse them, and never let either silently behave like the other.

## REDACT — remove
The original content is gone, structurally, from anything that leaves the system.
- **Mechanism (digital text):** build the output ONLY from the gaps between accepted spans. Characters inside `[start, end)` are never copied into the output. This is structural removal, not a visual cover over still-present data.
- **Proof:** a test asserts every accepted span's text is ABSENT from the output, while non-PII context (e.g. "Policy number:") is preserved.

## ANONYMIZE — replace
The content is swapped for a stable, type-aware placeholder; the document stays readable and internally consistent.
- **Mechanism:** each accepted span becomes a token like `[PERSON_1]`. The SAME entity maps to the SAME token at every occurrence. Distinct entities of the same type get distinct numbers (`[PERSON_1]`, `[PERSON_2]`).
- **Proof:** a test asserts same entity -> same token everywhere; same phone -> same token both times.

## The toggle
- `OutputMode` is a user choice in the UI, not a config flag.
- Both modes consume the SAME accepted-span set; only the output stage differs.
- Flipping the mode re-renders from that span set WITHOUT re-running detection.
- Export is computed server-side from the submitted span set so "what's shared" is authoritative. Return `{ output_text, legend[] }`.

## Raster warning (scanned documents)
For raster pages, REDACT means re-rendering the page image with the box region overwritten in PIXELS, then re-encoding the image. An overlay placed on top of still-extractable text or image data is NOT redaction — it is the exact "redacted but the data is still underneath" failure the product exists to prevent. Verify by attempting extraction on the output.
