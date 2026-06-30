"""Export route — thin. Resolves the accepted span set from the session and
hands it to the redaction service. No rendering logic lives here.
"""
from __future__ import annotations

from fastapi import APIRouter

from errors import AppError
from models.api import ExportRequest, ExportResponse
from services import redaction
from services.session_store import store

router = APIRouter(prefix="/api", tags=["export"])


@router.post("/export", response_model=ExportResponse)
def export(req: ExportRequest) -> ExportResponse:
    """Render REDACT/ANONYMIZE output from the submitted accepted-span set."""
    session = store.get(req.session_id)  # 404 -> typed error if unknown

    by_id = {s.id: s for s in session.spans}
    unknown = [sid for sid in req.accepted_span_ids if sid not in by_id]
    if unknown:
        raise AppError(
            status_code=400,
            error="unknown_span_id",
            detail=f"accepted_span_ids not found in session: {unknown}",
        )

    accepted = [by_id[sid] for sid in req.accepted_span_ids]
    output_text, legend = redaction.render(
        session.original_text, accepted, req.output_mode
    )
    return ExportResponse(output_text=output_text, legend=legend)
