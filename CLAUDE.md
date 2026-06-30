# Conseal Hackathon — Project Memory

You are helping a solo competitor win the Sprintfour "Conseal" hackathon. Conseal is a
desktop app that anonymizes documents by redacting/labeling PII so they can be safely
pasted into AI tools. The task is to build a **full-stack app** (real frontend + real
backend, wired together and runnable) that solves ONE of three problems well.

## The three problems (the competitor picks ONE)
1. **Trust & explainability** (Marcus): a skeptical user who won't adopt a tool he can't
   interrogate. Every hidden span needs a "why this?", every visible span a "why not that?".
2. **Working at volume** (Maya): a paralegal with 200 files to anonymize by EOD. Will
   abandon anything that slows her down. Batch throughput + speed under pressure.
3. **Fixing the tool's mistakes** (Sam): a fast, over-trusting reviewer correcting a tool
   that has BOTH false positives (harmless text hidden) and missed PII (real PII left
   visible). The dangerous mistakes are the ones he doesn't stop to look at.

## What actually wins (the rubric — internalize this)
Working code is the FLOOR, not the differentiator. Judges score:
- **SE fundamentals** — clean, well-structured code; sensible architecture; separation of
  concerns; clear naming; error handling; a project a teammate could pick up.
- **Discovery** — did you notice hard cases the prompt did NOT spell out?
- **Judgment** — did you spend effort on the part that actually matters?
- **Real-user empathy** — designed for the real person under real constraints, not a clean demo.
- **Tradeoff awareness** — recognized tensions and made a deliberate call.
- **Reasoning** — can explain choices, including what was left out.

Everyone has AI, so a working prototype is baseline. The signal is JUDGMENT: which hard
cases were noticed and how thoughtfully they were handled. Bias every decision toward
the chosen user's real behavior over demo polish.

## Deliverables
- The runnable app + clear start instructions.
- A ~half-page writeup: what was built AND what was deliberately NOT built, and why.
- A short demo (video or live walkthrough).

## PII detection is a means, not the point
Do NOT build a detector from scratch. Two accepted paths, neither scored higher:
- **Option A** — a cloud LLM with the user's own API key returns sensitive spans + types.
- **Option B** — a mock backend returning a fixed list of spans (text, type, confidence).
Pick whichever reaches the interesting UX work fastest. Build the seam so A and B are
interchangeable behind one interface.

## Your team of subagents (delegate deliberately)
- **product-strategist** — discovery, edge cases, user empathy, tradeoffs. Consult BEFORE
  building and whenever a design decision has tension. This is where the rubric is won.
- **pii-detection-engineer** — the detection layer (LLM prompt OR mock), span model,
  confidence, the A/B-interchangeable interface.
- **backend-engineer** — API, document handling, services, the redaction engine.
- **frontend-engineer** — the review experience; how it *feels* to use.
- **code-reviewer** — run after meaningful changes; guards SE fundamentals.
- **submission-writer** — the writeup + demo script; frames the reasoning judges read.

## Skills available (auto-loaded by description, also attached to agents)
- `conseal-domain` — the rubric, the three users, what judges reward, PII taxonomy.
- `pii-detection` — LLM prompt patterns, mock-backend shape, span/offset handling.
- `redaction-ux-patterns` — per-problem UX patterns, confidence display, correction flows.
- `fullstack-scaffold` — clean architecture, recommended stack, conventions, project layout.

## LOCKED PROBLEM: Sam — fixing the tool's mistakes
Build for Sam only. He reviews the tool's suggested redactions. The tool made two kinds of
error, and they are NOT symmetric — this asymmetry drives the entire design:
- **False positives** (harmless text hidden): VISIBLE (they're highlighted), LOW stakes
  (worst case a word is needlessly hidden), EASY to fix (un-redact). Cost = readability.
- **False negatives / missed PII** (a phone number and a name left visible): INVISIBLE (look
  like normal text), HIGH stakes (this IS the privacy leak the product exists to prevent),
  HARD to find (nothing draws the eye). Cost = catastrophic.
Sam is fast and over-trusting; the mistakes that slip through are the ones he doesn't stop on.

### The trap that separates winners from the field
The naive build renders the doc, highlights the redactions, lets Sam accept/reject. That
handles false positives perfectly and IGNORES the missed PII entirely — i.e. it misses the
whole point. A judge sees that in five seconds. The winning insight: **make the invisible
visible.** You must generate candidates over the UN-redacted text and pull Sam's eye to them.

### The missed-PII finder — THREE complementary lenses (the heart of the build)
1. **Format pass (regex):** phone / email / SSN / card / policy shapes in visible text.
   High precision, deterministic, cheap → catches the missed phone number directly.
2. **Entity-consistency pass (the differentiator):** take every value the tool redacted with
   high confidence and find any UN-redacted occurrence of that same value (or its sub-tokens)
   elsewhere. "You redacted 'Margaret Holloway' here but left 'Margaret' visible there." High
   precision, no model needed, and it catches the kind of inconsistency tools constantly make.
3. **Semantic pass (LLM/NER, optional):** novel names with no prior redaction to anchor on
   (e.g. a doctor's name next to a medical condition). Lower precision → flag as REVIEW, never
   auto-redact, to avoid crying wolf.

### Tradeoffs to name out loud (scored)
- **Asymmetric cost** → bias the UI toward surfacing potential leaks even at some false-alarm
  cost, because a missed leak is catastrophic and a false alarm is a one-key dismiss.
- **Alert fatigue / cry-wolf** → flag too much and Sam tunes it out and misses the real one.
  Mitigation: calibrate by lens (format+consistency = high precision, can suggest strongly;
  semantic = soft "review") and ALWAYS say WHY each item is flagged so the signal stays trusted.
- **Respect his speed** → don't slow him globally. Add friction ONLY on the risky items;
  make everything safe frictionless. His speed is the constraint, not a bug to fight.

### Attention model, not a document dump
Alongside the inline document, give Sam a prioritized **review queue** of only the decisions
that need him: missed-PII candidates, low-confidence redactions (likely false positives),
and consistency conflicts — each with one-glance context, a why-flagged line, and a one-key
action. Both add-missed and un-redact must be a single gesture. Everything reversible (undo).

### The demo money shot
The tool's output looks finished, yet it left a phone number — and the SAME number twice —
in plain text. A fast, trusting reviewer skims right past it; this tool pulls the eye straight
to it, one key redacts it, and a consistency badge shows the duplicate. Then un-redact an
obvious false positive in one key. Close on: "the confident mistakes are the ones Sam skims
past — this makes them the ones he can't."

### Use the seeded fixture
`fixtures/` contains a realistic document plus the tool's flawed suggestions and an answer
key (`expected-corrections.json`). Build the MockDetector to return `tool-suggestions.json`,
build the finder to recover everything in `expected-corrections.json`. It's your test oracle
AND your demo script in one.

## Working principles
- Build the shared core first (spans + detection seam + redaction engine + doc rendering),
  then the missed-PII finder, then Sam's review-queue UX. The finder is the differentiator —
  give it the most thought.
- Keep two clearly-separated detection services: the tool's original suggestions, and the
  missed-PII finder over visible text. That separation reads as good engineering on its own.
- Keep the detection seam swappable (mock ↔ LLM) so the UX is never blocked on detection.
- Prefer one sharp, deep flow over many shallow features. Cut ruthlessly and record cuts.
- Track every deliberate non-build — that list is half the writeup and a scored signal.
