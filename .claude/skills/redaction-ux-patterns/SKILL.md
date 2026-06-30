---
name: redaction-ux-patterns
description: >
  UX patterns for the Conseal redaction-CORRECTION experience (Sam — fixing the tool's
  mistakes). Use when designing or building the review surface: surfacing missed PII,
  the review queue / attention model, one-key correction gestures, confidence display,
  calibrated flagging, undo, and the demo flow. Includes brief notes on how the same surface
  generalizes to Marcus (trust) and Maya (volume).
---

# Redaction-correction UX — built for Sam

Sam reviews a tool's suggested redactions. He is fast and over-trusts the tool. The dangerous
mistakes are the ones he doesn't stop to look at. The job is to DIRECT HIS ATTENTION to the
risky stuff and make every correction a single, reversible gesture. Adapt, don't checklist.

## The core insight: make the invisible visible
Two error types, asymmetric:
- **False positives** (harmless text hidden): already highlighted, low stakes, easy to fix.
- **Missed PII / false negatives** (phone number, name left visible): invisible, high stakes,
  hard to find — NOTHING draws the eye. This is the whole point of Sam's problem.
The naive design (highlight redactions, click to accept/reject) handles false positives and
completely ignores missed PII. Don't build the naive design. Generate candidates over the
UN-redacted text and surface them. (Detection of those candidates lives in the `pii-detection`
skill — three lenses: format regex, entity-consistency, optional semantic.)

## The attention model: a review queue, not a document dump
Render the document inline (original text, redactions highlighted, candidates flagged), AND
give Sam a prioritized **queue of only the decisions that need him**, ordered by risk:
1. **Missed PII candidates** (high precision first: format + consistency, then semantic "review").
2. **Low-confidence redactions** — most likely false positives.
3. **Consistency conflicts** — same value redacted in one place, visible in another.
Everything the tool got confidently right is collapsed/quiet so it doesn't compete for attention.
Each queue item shows, at a glance: the text in its surrounding sentence, the type, a
**why-flagged line**, and a one-key action. Sam works a short list, he doesn't re-read the doc.

## Correction gestures (both must be one action, both reversible)
- **Add a missed span:** accept a flagged candidate with one key; OR select any visible text
  and redact it instantly (he'll catch things the finder didn't).
- **Un-redact a false positive:** one key to remove a redaction he disagrees with.
- **Undo** on everything, with visible history. People correcting a machine make their own
  mistakes; fear of an irreversible click is what slows a fast reviewer down.

## Calibrated flagging (the cry-wolf tradeoff)
Flag too much → Sam tunes the warnings out and misses the real one. Too little → he misses the
phone number. So calibrate by lens and SHOW WHY:
- **Format + consistency** = high precision → strong flag, can be pre-suggested for one-key accept.
- **Semantic** = lower precision → soft "review" flag, never auto-applied.
- Every flag carries its reason ("matches phone format", "you redacted this name elsewhere",
  "name next to a medical term") so the signal stays trustworthy. A trusted flag is the goal.

## Bias toward surfacing leaks (the asymmetry)
A missed leak is catastrophic; a false alarm is a one-key dismiss. So when in doubt, surface
it — but as a dismissible REVIEW item, not an auto-redaction. State this bias in the writeup.

## Confidence is visual
Encode confidence in color intensity / opacity so likely-wrong redactions (low confidence)
stand out as candidates for un-redaction. Don't bury it in a number-only tooltip.

## The export is the proof
"Redacted" must mean the original characters are GONE from the exported artifact. Let Sam view
exactly what will be shared. This matters even for Sam: his corrections are pointless if the
underlying text still leaks.

## Honest edge / empty states
Detection failed; zero suggestions; every redaction low-confidence; a candidate Sam dismisses;
a document with no PII at all. Design these — they're where rushed builds fall apart.

## Demo beat (drive this exact flow)
1. Show the tool's output — looks finished, some things blacked out.
2. Point at a phone number sitting in plain text. "Sam's fast and trusts the tool — he skims past this."
3. Your tool has already flagged it (with a consistency badge: same number appears twice). One key redacts both.
4. Un-redact an obvious false positive (a needlessly-hidden harmless word) in one key.
5. Close: "The confident mistakes are the ones Sam skims past — this makes them the ones he can't."

## Anti-patterns
A spans list with no sentence context. Relying on Sam's eye to find missed PII. Flagging so
much it becomes noise. Un-redacting being slower than adding (or vice versa). Irreversible
actions. Claiming "redacted" while the original survives in the payload. Building only the happy path.

---

## How the same surface generalizes (architecture note, not extra scope)
The shared core (document + spans + detection seam + redaction engine + review surface) also
serves the other two users — worth one sentence in the writeup, not a second build:
- **Marcus (trust):** the same "why-flagged" line and "view exactly what will be shared" export
  answer his "why this / why not that" and "prove it's gone".
- **Maya (volume):** the same keyboard-first queue, auto-quiet-the-certain, and surface-only-
  the-uncertain patterns scale to many files.
Do not build these out. Mention the seam to show judgment; keep depth on Sam.
