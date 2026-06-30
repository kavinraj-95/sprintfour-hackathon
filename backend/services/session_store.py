"""In-memory session store.

A deliberately thin service: it holds `SessionState` objects keyed by id for
the life of the process. Swapping this for a real persistence layer later means
changing only this file — routes depend on the small surface below, not on how
it stores anything. No detection happens here; a new session starts with no
spans (later layers add them).
"""
from __future__ import annotations

import uuid

from errors import AppError
from models.contract import OutputMode, SessionState


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, *, original_text: str, output_mode: OutputMode) -> SessionState:
        session_id = uuid.uuid4().hex
        state = SessionState(
            session_id=session_id,
            original_text=original_text,
            spans=[],
            output_mode=output_mode,
        )
        self._sessions[session_id] = state
        return state

    def get(self, session_id: str) -> SessionState:
        state = self._sessions.get(session_id)
        if state is None:
            raise AppError(
                status_code=404,
                error="session_not_found",
                detail=f"No session with id {session_id!r}.",
            )
        return state


# Process-wide singleton. Routes import this instance.
store = SessionStore()
