---
name: redaction-ux-patterns
description: >
  UX patterns for redaction-review interfaces, organized by the three Conseal problems
  (trust, volume, fixing-mistakes) plus shared patterns (span rendering, confidence display,
  undo, the missed-PII problem, proving the original is gone). Use when designing or building
  the review experience, choosing interactions, or deciding what to surface vs. hide.
---

# Redaction-review UX patterns

The heart of every Conseal problem is the experience. These are patterns to adapt, not a
checklist to implement wholesale. Pick the ones that serve the ONE chosen user; cut the rest.

## Shared foundations (any problem)
- **Document as the surface.** Render original text with spans highlighted in place. Don't
  show a list of spans divorced from context — decisions need the surrounding sentence.
- **Confidence is visual, not numeric-only.** Encode it in color intensity / opacity /
  border so the user triages at a glance; the exact number can live in a tooltip.
- **Color-code by type** so PERSON vs PHONE vs ADDRESS is scannable.
- **Every action is reversible.** Undo (and ideally a visible history). People correcting a
  machine make their own mistakes; fear of an irreversible click slows them down.
- **The export is the real artifact.** What gets shared must have the original sensitive
  characters removed/replaced — show the user the anonymized result, don't make them trust it.
- **Honest empty/edge states:** zero spans found, detection failed, every span low-confidence.

## Problem 1 — Trust & explainability (Marcus)
The job is to convert skepticism into confidence by making the tool interrogable.
- **"Why this?" on every redaction:** type, confidence, and a one-line reason, on hover/click.
- **"Why NOT that?":** let him probe visible text too — the tool should be able to say "I
  considered this and judged it non-identifying because…". A skeptic distrusts unexplained silence.
- **Prove removal, don't claim it.** A before/after or "view exactly what will be shared"
  that demonstrates the original characters are gone — directly answers his "still underneath" fear.
- **Surface the tool's uncertainty honestly.** Showing low-confidence calls as low-confidence
  earns more trust than false certainty.
- **Let him override and watch the export change** — agency is part of trust.
- Tension: completeness of explanation vs. overwhelming him. Explain on demand, not all at once.

## Problem 2 — Working at volume (Maya)
She has 200 files and won't read them. Design for triage and speed, not thoroughness.
- **Keyboard-first.** Accept / reject / next / undo all on keys; the mouse is the slow path.
  This single choice can be the differentiator.
- **Auto-handle the certain, queue the uncertain.** Auto-accept high-confidence spans; only
  stop her on the ones that actually need a human. Reading 200 fully is the wrong design.
- **Batch identical decisions.** "Redact all 47 instances of this client's name across all
  files" — decide once, apply everywhere.
- **A queue with progress and recovery.** Show N of 200, let her stop and resume; an interruption
  must not lose work.
- **One bad file doesn't stop the batch.** Skip-and-flag, keep moving.
- **Define "done."** A clear end state per file and for the batch, so she knows when to stop.
- Tension: speed vs. control. Default to fast with an escape hatch to inspect, not the reverse.

## Problem 3 — Fixing the tool's mistakes (Sam)
He's fast and over-trusting; the dangerous error is the one he doesn't stop on.
- **Two failure types, two flows:** false positives (un-redact, harmless text hidden) and
  missed PII (add a span over text the tool left visible). Make BOTH one gesture.
- **The hard half is the missed PII** — there's nothing highlighted to click. Help him find it:
  flag un-redacted text that pattern-matches PII (phone/email/SSN shapes) as "suspicious,
  review me"; let him select any text and redact it instantly. Don't rely on him noticing.
- **Pull the eye to risk.** Sort/highlight by what's most likely wrong: low-confidence
  redactions and suspicious un-redacted text first, so the skim-past failure is designed against.
- **Make over-trust expensive to act on, cheap to correct.** A second's friction on the
  risky items, frictionless undo everywhere.
- Tension: flag too much and he tunes it out; too little and he misses the phone number.
  Calibrate to the genuinely-uncertain, and say why each item is flagged.

## Anti-patterns (any problem)
- A spans list with no document context. A modal per span at volume. Confidence hidden in a
  tooltip when it should drive the layout. Irreversible actions. Claiming "redacted" while the
  original text survives in the payload. Designing the happy path and ignoring malformed
  input / zero results / detection failure.
