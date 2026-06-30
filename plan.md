# Conseal — Problem 3 (Sam): Redaction-Correction App

## Context
Sprintfour "Conseal" hackathon, solo build. **Problem 3 is locked: Sam — fixing the tool's mistakes.**
Sam reviews a redaction tool's suggestions while moving fast and over-trusting it. The tool makes
two *asymmetric* errors: **false positives** (harmless text hidden — visible, low-stakes, easy to
un-redact) and **false negatives / missed PII** (a phone number and a name left visible — invisible,
catastrophic, hard to find). The naive build (highlight redactions → accept/reject) handles false
positives and completely ignores missed PII — that is the trap a judge spots in five seconds.

**Thesis:** *The tool's most confident output is exactly where Sam stops looking. Conseal turns the
misses he'd skim past into a short, risk-ranked queue he can't miss — each correction one reversible
keystroke — and proves the leak is gone from the export.*

The repo already contains the test oracle: `fixtures/sample-document.txt`, `tool-suggestions.json`
(what the flawed tool returns — 2 low-confidence false positives, and it MISSES all real leaks), and
`expected-corrections.json` (what a perfect Sam session recovers). The finder must recover every
`add_missed_pii` entry with the right lens; the UX must flag both `remove_false_positives` items.

**Decisions made with the user:** Backend = **Python + FastAPI + Pydantic**; Frontend =
**React + Vite + TypeScript + Tailwind**. Detection is **mock-first** (deterministic, offline demo)
but the `Detector`/lens seam is built and flag-gated so a real cloud LLM can be added later.

Verified offsets into `sample-document.txt` (len 616) that drive the design:
- `Margaret Holloway` (s1) = `[44,61)`. Sub-token `Margaret` occ1 `[44,52)` is INSIDE s1 → must NOT be
  flagged; occ2 `[118,126)` is visible → MUST be flagged (lens `consistency`).
- `0412 887 905` occ1 `[208,220)` → lens `format`; occ2 `[518,530)` → lens `format+consistency`
  (same number twice = duplicate-visible conflict). Both visible, both leak.
- `Dr. Raymond Pike` `[285,301)` — never redacted, no anchor → lens `semantic`, review-only.
- False positives to flag: `Coastline Mutual` (0.58), `Sydney` (0.49).

## Project layout (to be created)
```
/backend
  app.py                 # FastAPI app, CORS, router include, global typed error handler
  config.py              # DETECTOR=mock|llm, SEMANTIC_LENS flag, model id + key from env
  /routes
    session.py           # POST /api/session/init, GET /api/session/{id}
    export.py            # POST /api/export (authoritative redaction)
  /services
    document.py          # load fixture / accept pasted text; in-memory DocumentStore
    offsets.py           # OccurrenceResolver: (text, value, 1-based occurrence) -> (start,end)
    redaction.py         # RedactionEngine.apply() -> anonymized artifact + legend
    missed_pii_finder.py # MissedPiiFinder orchestrator (THE differentiator)
    /lenses
      format_lens.py     # regex shapes over visible text
      consistency_lens.py# propagate confident redactions + duplicate-visible conflicts
      semantic_lens.py   # LLM lens (flag-gated) + MockSemanticLens for offline tests
  /detectors
    base.py              # Detector protocol: detect(text) -> list[Span]
    mock_detector.py     # returns EXACTLY tool-suggestions.json, resolved to offsets
    llm_detector.py      # cloud LLM, server-side only (stub, flag-gated)
    factory.py           # get_detector() reads DETECTOR
  /models
    span.py              # Span, Candidate, Conflict, PiiType  (shared contract)
    api.py               # request/response models + ErrorResponse
  /tests
    test_detector_seam.py
    test_redaction.py
    test_finder_oracle.py
  requirements.txt
/frontend/src
  /api/client.ts         # one typed client: initSession(), exportDocument()
  /types/span.ts         # mirrors backend Span/Candidate/Conflict/PiiType
  /state/useSession.ts   # session + working corrections
  /state/useHistory.ts   # undo stack (every gesture reversible)
  /components/DocumentView.tsx, Token.tsx, ReviewQueue.tsx, QueueItem.tsx,
              ConflictBadge.tsx, ExportPanel.tsx, ShortcutHints.tsx
  App.tsx, main.tsx
README.md                # two-command run
```
**SE-fundamentals signal:** thin routes, fat services; detection and finding are *two physically
separate modules* (`/detectors` vs `services/missed_pii_finder.py`); one typed contract mirrored on
both sides; typed errors, never bare 500.

## Shared contract (`models/span.py` ↔ `types/span.ts`)
- `PiiType` enum: PERSON, ORG, EMAIL, PHONE, ADDRESS, DOB, SSN, ACCOUNT, IP, URL, CASE_NUMBER,
  POLICY_NUMBER, LOCATION, MEDICAL, CREDENTIAL.
- `Span { id, start, end, text, type, confidence, reason, source:"tool"|"manual" }` — a redaction.
- `Candidate { id, start, end, text, type, lens:"format"|"consistency"|"format+consistency"|"semantic",
  severity:"suggest"|"review", reason, conflict? }` — a MISS over visible text.
- `Conflict { kind:"redacted-elsewhere"|"duplicate-visible", locations:[{start,end}] }`.
- `SessionState { session_id, text, spans[], candidates[] }`.
- Offset rule written down once: **codepoint offsets** into original text (doc is ASCII; JS uses
  `Array.from` slicing). `text === original[start:end]` asserted everywhere.

## API
| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/session/init` | `{ document_text? }` (omit → fixture) | `SessionState` |
| GET  | `/api/session/{id}` | — | `SessionState` |
| POST | `/api/export` | `{ session_id, active_span_ids[], accepted_candidate_ids[], style:"placeholder"\|"blackout" }` | `{ anonymized_text, legend[] }` |

`init` pipeline: detector → `OccurrenceResolver` → normalize → `MissedPiiFinder` over visible text →
return. Deterministic under `DETECTOR=mock`. Errors → typed `ErrorResponse` (422 bad input, 502 LLM
fail). Export is computed **server-side** from the submitted span set so "what's shared" is authoritative.

## MissedPiiFinder — the differentiator (most depth)
`find(text, redacted_spans) -> Candidate[]`. Separate service from any `Detector`.
Shared guard `is_visible(start, end, redacted_spans)` = range overlaps no redacted span — the universal
double-flag guard (this is what excludes `Margaret` occ1 inside s1 while keeping occ2).

1. **Format lens** (`lenses/format_lens.py`, regex, high precision, always on): compiled patterns per
   type — PHONE (digit groups w/ optional spaces/dashes/parens, length-validated, word-boundary),
   EMAIL, SSN, ACCOUNT (Luhn), IP, URL, POLICY/CASE. Emit only `is_visible` hits as
   `suggest`. **Deliberately does NOT flag bare years (`2022`) or generic dates** — calibration discipline.
2. **Consistency lens** (`lenses/consistency_lens.py`, no model, the differentiator):
   - **2a Propagate confident redactions:** for each redacted span with `confidence ≥ 0.85`, take the
     value + meaningful sub-tokens (whitespace split, drop titles/stop-tokens, len ≥ 3, proper-noun-ish),
     find `is_visible` occurrences elsewhere → `Candidate(lens="consistency", conflict=redacted-elsewhere)`.
     s1 (0.97) → `Margaret` occ2 emitted, occ1 excluded. Low-confidence s3/s4 below threshold → not
     amplified.
   - **2b Duplicate-visible conflict:** group all candidates so far by normalized value (digits-only for
     phones, casefold for names); any value at ≥2 visible spots → later occurrences get `+consistency`
     and `conflict=duplicate-visible`. The phone group → occ2 becomes `format+consistency`.
3. **Semantic lens** (`lenses/semantic_lens.py`, LLM, flag-gated, `review`-only): prompt over the
   redaction-applied text for missed identifying info (names near medical/financial context); validate
   JSON, re-anchor via resolver, `is_visible`. Emits `severity="review"` only — never auto-redact.
   `MockSemanticLens` returns `Dr. Raymond Pike` so tests pass offline.
4. **Merge/calibrate tail:** final `is_visible` drop → coalesce overlapping candidates (union lens tags,
   merge conflicts) → severity by lens (format/consistency=`suggest`, semantic=`review`) → sort by risk
   (consistency-conflict, then format, then semantic; ties by `start`).

## Redaction engine (`services/redaction.py`)
`apply(text, spans, style) -> (anonymized_text, legend)`. Sort accepted spans, assert non-overlapping,
**build output only from the gaps between spans** — characters in `[start,end)` are never copied
(structural removal proof, not a visual cover). Placeholder style = `[PHONE]` / stable `[PERSON_1]`;
blackout = `█`×len. `legend` = placeholder → type → count for the export panel. Value-level redaction
("redact this value everywhere") is first-class so one key redacts BOTH phone occurrences.

## Frontend (Sam's attention model)
Landing view is the **risk-ordered ReviewQueue** (missed PII → low-confidence FPs → consistency
conflicts), each item = sentence context + why-flagged line + one-key action + `ConflictBadge` when
applicable. `DocumentView` is secondary: redactions + candidate highlights, **confidence shown as
opacity**. One-key reversible gestures: accept candidate, un-redact FP, select-to-redact (with "also
found in N places" propagation). `useHistory` undo. `ExportPanel` = "view exactly what will be shared"
(proof both phone occurrences are gone). Honest empty/degraded states: report **which lenses ran**,
never declare the doc "clean" (that rebuilds Sam's over-trust).

## Tradeoffs to name in the writeup
1. **Asymmetric cost** → bias toward surfacing leaks; when in doubt surface as dismissible REVIEW, never
   auto-redact. Cost: a few one-key dismissals.
2. **Cry-wolf** → calibrate by lens (format/consistency = strong `suggest`; semantic = soft `review`);
   propagate only `conf ≥ 0.85`; every flag carries a reason. Cost: a novel name with no cue slips — owned honestly.
3. **Respect his speed** → quiet everything the tool got confidently right; friction only on risk. Cost:
   no at-a-glance audit of confident-correct redactions (that's Marcus's job, not Sam's).
4. **Consistency precision** → word-boundary, proper-noun-token matching only, so the "redacted elsewhere"
   badge stays believable. Cost: misses nicknames/morphology ("Maggie", "Ms. Holloway").

## Deliberately NOT building (cut list = half the writeup)
Multi-file/batch (that's Maya) · PDF/DOCX parsing (plain-text fixture only) · live-LLM dependency for the
demo (mock + MockSemanticLens; LLM is a flag-gated extra) · fuzzy/nickname name matching (honest limit) ·
generic date/year flagging (deliberately noisy) · user-tunable thresholds (invites cry-wolf) · full
undo-timeline (single-level undo kills click-fear) · auth/DB/persistence/theming/mobile (zero rubric value).

## Build sequence (8h solo)
1. **0:00–0:30** Scaffold backend + frontend, fixtures path, two-command run skeleton.
2. **0:30–1:30** `models/span.py` + `types/span.ts`; `OccurrenceResolver`; `MockDetector` → `test_detector_seam` green.
3. **1:30–2:30** `RedactionEngine` + `/api/export` → `test_redaction` green (removal proven early).
4. **2:30–4:30** **MissedPiiFinder**: format + consistency (2a/2b) + orchestrator + MockSemanticLens →
   `test_finder_oracle` green. *Most time here.*
5. **4:30–5:00** `/api/session/init` + GET; typed errors; empty/failed states.
6. **5:00–7:00** Frontend: DocumentView, risk-ordered ReviewQueue + ConflictBadge, one-key add/un-redact,
   undo, ExportPanel proof.
7. **7:00–7:30** Optional (per user): wire real `LLMDetector` + real semantic lens behind flags.
8. **7:30–8:00** code-reviewer pass; README verify from clean clone; submission-writer half-page + demo script.

## Verification
- `cd backend && pytest` → all three tests green: detector determinism + offset integrity;
  **redaction removal** (every accepted `span.text` absent from export, gaps like "Policy number:" preserved);
  **finder vs oracle** (all 4 `add_missed_pii` recovered with correct lens incl. `format+consistency` for
  phone occ2 and `consistency` for Margaret; s3/s4 surfaced as the false positives).
- Two-command run: backend `uvicorn app:app --reload`, frontend `npm run dev`; load fixture, walk the demo
  money-shot beats (phone ×2 one-key, Margaret sub-token, Dr. Pike review, un-redact Sydney, export proof).

## Demo money-shot
Tool output looks finished (name + policy blacked out) → point at the visible phone → queue already ranks
it #1 with a consistency badge (same number twice) → one key redacts BOTH → `Margaret` sub-token one key →
`Dr. Raymond Pike` soft REVIEW (lower-confidence styling) one key → un-redact `Sydney` one key → export
preview proves both phone occurrences gone. Close: *"The confident mistakes are the ones Sam skims past —
this makes them the ones he can't."*
