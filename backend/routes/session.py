"""Session routes — thin. They validate input, call a service, return its result.

No business logic lives here: creating and fetching sessions is the store's job,
and detection is a later layer's job. The route's only responsibility is the
HTTP shape.
"""
from __future__ import annotations

from fastapi import APIRouter

from models.api import InitSessionRequest, InitSessionResponse
from models.contract import SessionState
from services.session_store import store

router = APIRouter(prefix="/api/session", tags=["session"])


@router.post("/init", response_model=InitSessionResponse)
def init_session(req: InitSessionRequest) -> SessionState:
    """Start a review session over pasted/loaded text. Spans come later."""
    return store.create(original_text=req.text, output_mode=req.output_mode)


@router.get("/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    """Fetch a session's current state (404 -> typed error envelope)."""
    return store.get(session_id)
