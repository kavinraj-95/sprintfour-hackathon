"""API request/response models — the typed boundary for each endpoint.

Bodies live here (not in routes) so the wire format is described in one place
and the routes stay thin. The contract types (Span, SessionState, ...) come
from `models.contract`; this module only adds the request/response envelopes
that wrap them.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from models.contract import OutputMode, SessionState


class ErrorResponse(BaseModel):
    """Uniform error envelope. Every failure returns this, never a bare 500."""

    error: str = Field(description="Stable, machine-readable error code.")
    detail: str | None = Field(default=None, description="Human-readable explanation.")


class InitSessionRequest(BaseModel):
    """Start a review session over a block of text.

    No spans are supplied: detection runs in later layers. A fresh session
    therefore starts with an empty span list.
    """

    text: str = Field(min_length=1, description="The document text to review.")
    output_mode: OutputMode = OutputMode.REDACT


# A session's full state is returned as-is; no separate response wrapper needed.
InitSessionResponse = SessionState
