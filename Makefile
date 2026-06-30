# Two-command run. In two terminals:
#   make backend     # FastAPI on http://localhost:8000
#   make frontend    # Vite dev server on http://localhost:5173
#
# Each target is self-contained: it installs its own dependencies on first run,
# then starts the dev server with hot reload.

.PHONY: backend frontend test

backend:
	cd backend && python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt && .venv/bin/python -m spacy download en_core_web_sm && .venv/bin/uvicorn app:app --reload --port 8000

frontend:
	cd frontend && npm install && npm run dev

test:
	cd backend && .venv/bin/python -m pytest -q
