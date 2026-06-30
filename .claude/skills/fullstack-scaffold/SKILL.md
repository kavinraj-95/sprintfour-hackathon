---
name: fullstack-scaffold
description: >
  Clean full-stack architecture and conventions for the Conseal hackathon prototype:
  recommended stack, project layout, the route/service/detector separation, the typed API
  seam between frontend and backend, error-handling conventions, and what to deliberately
  NOT add. Use when scaffolding the project, choosing structure, or reviewing whether the
  code will score on SE fundamentals.
---

# Full-stack scaffold & conventions

Optimized for a solo 8-hour prototype that reads like a competent team wrote it. Judges score
SE fundamentals directly, so structure and clarity matter as much as functionality.

## Recommended stack (swap if you're faster in another)
- **Frontend:** React + Vite + TypeScript + Tailwind. Fast dev loop, typed, clean.
- **Backend:** Python + FastAPI + Pydantic (typed request/response models map cleanly to the
  span contract and PII work is natural in Python). Node + Fastify/Express + TypeScript is an
  equally fine choice if you'd rather stay one-language. Pick one and commit; don't dither.
- **State:** in-memory store behind a clean interface is fine for a prototype and easier to
  read than a database. Add persistence only if the chosen problem needs it.
- **Detection:** behind the `Detector` interface (see `pii-detection`), `DETECTOR=mock|llm`.

## Project layout (separation of concerns is the point)
```
/backend
  /routes        # thin: validate input, call a service, shape the response
  /services      # business logic: document, detection, redaction
  /detectors     # MockDetector + LLMDetector behind one interface
  /models        # span + document schemas (Pydantic / types) — the shared contract
  /tests         # detection seam + redaction engine at minimum
/frontend
  /src
    /api         # one typed client; no fetch() scattered through components
    /components  # small, focused, well-named
    /state       # colocated sensibly; no global god-store
    /types       # span/document types mirroring the backend contract
README.md        # how to run it, in two commands
```

## Conventions that earn the SE-fundamentals score
- **Thin routes, fat services.** No business logic in routes or in React components.
- **One source of truth for the span/document shape**, mirrored on both sides. When the
  contract changes, it changes in one place.
- **Typed boundaries.** Pydantic models / TS types at every seam. No `any`, no untyped dicts
  flowing through the app.
- **Error handling is not optional** (it's scored): validate inputs; return typed errors with
  useful messages; never bare-500 on a malformed document; at volume one bad file is skipped
  and flagged, not fatal; the frontend renders detection-failed / empty / zero-spans states.
- **Names say what things are.** Functions do one thing. Files stay small. No god-files.
- **A two-command run.** `README` start instructions that actually work from a clean clone —
  the handout explicitly asks for clear instructions to start it.
- **Tests where the stakes are:** the detection seam (deterministic via mock) and the
  redaction engine (prove the original text is gone). A couple of focused tests > zero.

## Deliberately do NOT add (and note these as cuts in the writeup)
- Auth, user accounts, real database, job queues, multi-format file parsing, deployment infra
  — unless the chosen problem genuinely requires it. Each one you skip to go deeper on the
  core flow is a tradeoff worth stating. Over-engineering reads as poor judgment here, not effort.

## Suggested build order (solo, 8 hours)
1. Lock the ONE problem and the one-sentence thesis (consult product-strategist).
2. Span contract + `MockDetector` so the pipeline is real and deterministic on day one.
3. Backend: ingest → detect → return spans → accept corrections → export anonymized artifact.
4. Frontend: render doc + spans, the core interaction for the chosen user, undo, confidence.
5. The one hard case that proves discovery (e.g. missed-PII finding, or prove-removal export).
6. code-reviewer pass; then LLMDetector if time allows; then submission-writer.
Stop adding features the moment the core flow is deep and correct. Depth beats breadth.
