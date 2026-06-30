"""Review routes — thin. They marshal HTTP to the review service and back.

The correction surface the frontend builds on:
  POST /api/review                 -> run detection, return the queue (ReviewState)
  GET  /api/review/{id}            -> current ReviewState
  POST /api/review/{id}/action     -> apply one reversible gesture, return ReviewState
  POST /api/review/{id}/preview    -> live REDACT/ANONYMIZE preview from accepted set
  POST /api/review/{id}/export     -> export, or a gate listing unresolved high-risk
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter

from models.api import (
    ActionRequest,
    CreateReviewRequest,
    ExportResponse,
    ExportResult,
    ExportReviewRequest,
    PreviewRequest,
    ReviewState,
)
from services import review

router = APIRouter(prefix="/api/review", tags=["review"])


@router.post("", response_model=ReviewState)
def create_review(req: CreateReviewRequest) -> ReviewState:
    session = review.create(
        session_id=uuid.uuid4().hex,
        text=req.text,
        output_mode=req.output_mode,
        run_llm=req.run_llm,
    )
    return review.state(session)


@router.get("/{session_id}", response_model=ReviewState)
def get_review(session_id: str) -> ReviewState:
    return review.state(review.store.get(session_id))


@router.post("/{session_id}/action", response_model=ReviewState)
def act(session_id: str, req: ActionRequest) -> ReviewState:
    session = review.store.get(session_id)
    review.apply_action(
        session, type=req.type, target_id=req.target_id,
        start=req.start, end=req.end, pii_type=req.pii_type,
    )
    return review.state(session)


@router.post("/{session_id}/preview", response_model=ExportResponse)
def preview(session_id: str, req: PreviewRequest) -> ExportResponse:
    session = review.store.get(session_id)
    output_text, legend = review.render_preview(session, req.output_mode)
    return ExportResponse(output_text=output_text, legend=legend)


@router.post("/{session_id}/export", response_model=ExportResult)
def export(session_id: str, req: ExportReviewRequest) -> ExportResult:
    session = review.store.get(session_id)
    return review.export(session, req.output_mode, confirm=req.confirm)
