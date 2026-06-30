"""API request/response models — the typed boundary for each endpoint.

Bodies live here (not in routes) so the wire format is described in one place
and the routes stay thin. The contract types (Span, SessionState, ...) come
from `models.contract`; this module only adds the request/response envelopes
that wrap them.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from models.contract import OutputMode, PiiType, SessionState


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


class ExportRequest(BaseModel):
    """Render the chosen output from a SUBMITTED set of accepted spans.

    The accepted set is authoritative: the server renders only what is listed
    here, so "what gets shared" is exactly what the client confirmed. Flipping
    `output_mode` re-renders from the same span set; detection never re-runs.
    """

    session_id: str
    accepted_span_ids: list[str] = Field(
        default_factory=list,
        description="Ids (from the session's spans) the user confirmed to act on.",
    )
    output_mode: OutputMode


class LegendEntry(BaseModel):
    """One row of the export key. Carries NO raw PII, so the legend is safe to
    share alongside the output: it describes WHAT was removed/replaced, not the
    sensitive value itself."""

    token: str = Field(description="What appears in the output (a marker, or [TYPE_n]).")
    type: PiiType
    occurrences: int = Field(description="How many places this entity was acted on.")


class ExportResponse(BaseModel):
    output_text: str
    legend: list[LegendEntry]
