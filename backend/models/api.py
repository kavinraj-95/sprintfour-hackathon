"""API request/response models — the typed boundary between client and server.

Only the error envelope lives here for now; request/response bodies for the
session and export endpoints are added alongside those routes.
"""
from __future__ import annotations

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Uniform error envelope. Every failure returns this, never a bare 500."""

    error: str
    detail: str | None = None
