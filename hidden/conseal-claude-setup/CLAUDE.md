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

## Working principles
- Decide the ONE problem first; let every later choice serve that user.
- Keep the detection seam swappable (A↔B) so the UX is never blocked on detection.
- Prefer one sharp, deep flow over many shallow features. Cut ruthlessly and record cuts.
- Track every deliberate non-build — that list is half the writeup and a scored signal.
