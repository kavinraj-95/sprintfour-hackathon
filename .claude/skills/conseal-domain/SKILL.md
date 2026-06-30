---
name: conseal-domain
description: >
  Domain context for the Sprintfour Conseal hackathon. Use whenever a decision depends on
  what the judges reward, who the three users are, what counts as a "hard case", PII types,
  or how "redacted" must actually behave. The shared source of truth for the rubric and the
  problem space so every agent optimizes for the same win condition.
---

# Conseal Hackathon — Domain Knowledge

## What Conseal is
A desktop app that anonymizes documents by redacting or labeling PII so they can be pasted
into AI tools without leaking private data. The real product runs 100% locally. For the
hackathon, cloud LLMs/APIs are explicitly allowed — focus on the experience, not local infra.

## The win condition (memorize)
Working code is the FLOOR. The differentiator is JUDGMENT. Scored criteria:
- **SE fundamentals** — clean, structured code; sensible architecture; separation of
  concerns; clear naming; error handling; a teammate could pick it up.
- **Discovery** — noticing hard cases the prompt did not spell out.
- **Judgment** — effort spent on the part that actually matters.
- **Real-user empathy** — built for the real person under real constraints, not a demo.
- **Tradeoff awareness** — tensions recognized and a deliberate call made.
- **Reasoning** — choices explainable, including what was left out.

Implication: a narrow, deep, correct flow for one user, plus a crisp account of the
tradeoffs and the cuts, beats a broad shallow feature set every time.

## The three users — pick ONE, build deep
**Marcus — Trust & explainability.** Skeptical; been burned by "redacted" docs that still
had the data underneath. Won't adopt a tool he can't interrogate. Needs "why was this
hidden?" for every redaction and "why was this kept?" for every non-redaction. Win by
making the tool's reasoning legible and by proving the original never leaks.

**Maya — Working at volume.** Paralegal, 200 files by EOD, currently one at a time. Fast,
under pressure, abandons anything that slows her down. She will not read 200 files — design
for triage and throughput: keyboard-first, auto-handle the certain, surface only the
uncertain, batch repeated decisions, survive interruption, never block on one bad file.

**Sam — Fixing the tool's mistakes.** Reviews suggested redactions; the tool has BOTH false
positives (harmless text hidden) and missed PII (a phone number and a name left visible).
He moves fast and trusts the tool too much — the mistakes that slip through are the ones he
doesn't stop to look at. Win by pulling his eye to the dangerous error and making both
corrections (un-redact / add-missed) a single fast gesture.

## Hard cases worth discovering (not exhaustive — keep hunting)
- "Redacted but still underneath": is the original text actually removed from the shared
  artifact, or just visually covered? This is the trust failure mode and a correctness bug.
- Context-dependent PII: a name alone may be fine; name + medical condition is not.
- Overlapping / nested / duplicate spans; the same string appearing in many places.
- Low-confidence spans: who decides, and how is the decision surfaced?
- False NEGATIVES are the scary ones — text the tool left visible. Hardest to design for
  because there's nothing highlighted to click. Make suspicious un-redacted text findable.
- At volume: malformed file shouldn't break the batch; "done" must be definable; progress
  must survive an interruption.
- Proving a non-redaction: convincing a skeptic WHY something was correctly left visible.

## PII type taxonomy (typical)
PERSON, ORG, EMAIL, PHONE, ADDRESS, DATE_OF_BIRTH, SSN / national id, ACCOUNT / card number,
IP_ADDRESS, URL, CASE / file number, MEDICAL, CREDENTIAL. Each detected span should carry a
type, a confidence, and ideally a one-line reason (drives the "why this?" explanation).

## What "redacted" must mean
For the shared/exported artifact, the original sensitive characters should be GONE — replaced
by removal or a typed placeholder like `[PHONE]` / `[PERSON_1]`. Visually covering text while
the original stays in the underlying data is exactly the failure Marcus fears. Verify the
export, don't assume it.

## Detection: a means, not the point
Two accepted, equally-scored paths behind ONE interface:
- **Cloud LLM** with the competitor's own key → realistic, messy spans to design around.
- **Mock backend** → fixed spans (text, type, confidence) for a sample doc, zero setup.
Build them interchangeable so the UX never waits on detection. See the `pii-detection` skill.
