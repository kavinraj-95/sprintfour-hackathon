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


# ----------------------------------------------------------- review queue ----
# DTOs for the correction experience. The frontend mirrors these. `tier` is an
# int (1=high, 2=low-confidence, 3=soft-review) — the same vocabulary the merge
# step ranks by.


class OccurrenceRef(BaseModel):
    start: int
    end: int


class LayerStatus(BaseModel):
    """Honest report of one detection layer, for the 'what ran' panel."""

    name: str
    status: str  # "ok" | "skipped" | "error"
    count: int
    detail: str


class ReviewItem(BaseModel):
    """One row of the risk-ranked queue: a finding plus the reviewer's decision
    and one-glance sentence context."""

    id: str
    start: int
    end: int
    text: str
    type: PiiType
    confidence: float
    sources: list[str]
    reason: str
    normalized_value: str | None = None
    tier: int                              # 1 high, 2 low-confidence, 3 soft
    linked: list[OccurrenceRef] = Field(default_factory=list)
    linked_count: int = 0                  # other places this same value appears
    status: str                            # "pending" | "accepted" | "dismissed"
    sentence: str                          # context to show without opening the doc


class ReviewCounts(BaseModel):
    tier1: int
    tier2: int
    tier3: int
    accepted: int
    dismissed: int
    pending: int
    unresolved_high_risk: int              # tier-1 items still pending -> gates export


class ReviewState(BaseModel):
    """The whole correction surface in one payload: the queue, what ran, counts,
    and the live output mode."""

    session_id: str
    original_text: str
    output_mode: OutputMode
    layers: list[LayerStatus]
    queue: list[ReviewItem]
    counts: ReviewCounts


class CreateReviewRequest(BaseModel):
    text: str = Field(min_length=1)
    output_mode: OutputMode = OutputMode.REDACT
    run_llm: bool = False


class ActionRequest(BaseModel):
    """A single reversible gesture. `accept`/`dismiss` target an existing item;
    `add_missed` creates a manual span from a text selection; `undo` reverts the
    most recent action."""

    type: str  # "accept" | "dismiss" | "add_missed" | "undo"
    target_id: str | None = None
    start: int | None = None
    end: int | None = None
    pii_type: PiiType | None = None


class PreviewRequest(BaseModel):
    output_mode: OutputMode


class ExportReviewRequest(BaseModel):
    output_mode: OutputMode
    confirm: bool = False  # second deliberate action, required when gated


class ExportResult(BaseModel):
    """Either the rendered artifact, or a gate listing the unresolved high-risk
    items. `gated=True` means nothing was rendered — the export was held back."""

    gated: bool
    output_text: str | None = None
    legend: list[LegendEntry] = Field(default_factory=list)
    unresolved: list[ReviewItem] = Field(default_factory=list)
