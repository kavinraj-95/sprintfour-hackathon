# Conseal — Redaction Correction

A desktop-style tool for **Sam**, a fast, over-trusting reviewer correcting an
automated PII-redaction tool that makes two _asymmetric_ mistakes: harmless text
needlessly hidden (visible, low-stakes) and real PII left in plain sight
(invisible, catastrophic). Conseal's job is to **make the invisible misses
visible** so Sam can't skim past them.

> Status: **scaffold + shared contract**. The runnable skeleton and the typed
> data model are in place; detection layers, the missed-PII finder, and the
> review UX are built in later steps.

## Stack

| Layer    | Tech                                            |
| -------- | ----------------------------------------------- |
| Backend  | Python · FastAPI · Pydantic v2                   |
| Frontend | React · Vite · TypeScript · Tailwind CSS v4      |

## Run it (two commands)

You need **Python 3.11+** and **Node 18+**. Open two terminals from the repo root:

```bash
make backend      # FastAPI on http://localhost:8000  (creates a venv, installs, runs)
```

```bash
make frontend     # Vite dev server on http://localhost:5173  (npm install, runs)
```

Then open **http://localhost:5173**. The page shows the backend health
(`ok · detector=mock`) and lets you start a review session — proving the typed
client ↔ server seam end-to-end. The Vite dev server proxies `/api/*` to the
backend, so there's nothing else to configure.

Prefer raw commands instead of `make`? They are exactly:

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt \
  && .venv/bin/uvicorn app:app --reload --port 8000

# frontend
cd frontend && npm install && npm run dev
```

### Tests

```bash
make test         # backend pytest: contract round-trip + offset-rule enforcement
```

## Architecture

The rule is **thin routes, fat services**. A route validates input, calls a
service, and returns the result — no business logic. Detection layers (later)
each live in their own service module behind one interface, so the UX is never
blocked on detection and the mock ↔ LLM seam stays swappable.

```
backend/
  app.py                 # FastAPI app: CORS, typed error handlers, router wiring (thin)
  config.py              # env-driven config; names the DETECTOR seam (mock|llm)
  errors.py              # AppError — the one domain error type; no bare 500s
  models/
    contract.py          # THE SHARED CONTRACT (mirrored in frontend) + the offset rule
    api.py               # per-endpoint request/response envelopes + ErrorResponse
  routes/
    session.py           # POST /api/session/init, GET /api/session/{id} (thin)
  services/
    spans.py             # make_span(): the ONE span-creation site; asserts the offset rule
    session_store.py     # in-memory SessionState store
  tests/
    test_contract.py     # offset rule + contract round-trip

frontend/
  src/
    types/contract.ts    # the contract, mirrored field-for-field from the backend
    api/client.ts        # typed fetch client; throws ApiError from the error envelope
    App.tsx              # scaffold page: health probe + session round-trip
```

### The shared contract

One data model, expressed twice and kept in lockstep
(`backend/models/contract.py` ⇄ `frontend/src/types/contract.ts`):

- **`PiiType`** — `PERSON · ORG · EMAIL · PHONE · ADDRESS · ID_NUMBER · OTHER`
  (deliberately small; types are added only when a detection layer produces them).
- **`Span`** — `{ id, start, end, text, type, confidence (0–1), source, reason }`
  where `source ∈ regex | dictionary | ner | llm | manual`.
- **`OutputMode`** — `REDACT | ANONYMIZE`.
- **`SessionState`** — `{ session_id, original_text, spans[], output_mode }`.

### The offset rule (load-bearing)

A span's offsets are **codepoint indices** into `original_text`, with `end`
exclusive, and for **every** span:

```
span.text == original_text[span.start : span.end]
```

Spans are never built ad hoc — they go through `make_span`, the single creation
site that holds both the claimed text and `original_text`, where the rule is
asserted. A mismatch raises a typed error rather than silently redacting the
wrong slice. (Codepoints, not byte/UTF-16 units, so Python `str` and JS string
indexing agree; the frontend mirrors with `Array.from` for astral characters.)

### Error handling

Every failure returns the uniform `ErrorResponse` envelope
(`{ error, detail }`) — domain errors, request-validation errors, and even
unexpected exceptions are all caught and typed. **Never a bare 500.**
```
