"""Scaffold-level tests: the contract holds and the offset rule is enforced.

No detection is exercised here — only that the shared types round-trip and that
`make_span` actually guards the offset invariant the whole system relies on.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import app
from errors import AppError
from models.contract import OutputMode, PiiType
from services.spans import make_span

TEXT = "Call Margaret Holloway on 0412 887 905."

client = TestClient(app)


def test_make_span_enforces_offset_rule() -> None:
    # Margaret Holloway occupies [5, 22) in TEXT.
    span = make_span(
        id="t1",
        original_text=TEXT,
        start=5,
        end=22,
        type=PiiType.PERSON,
        confidence=0.97,
        source="manual",
        reason="full name",
        text="Margaret Holloway",
    )
    assert span.text == TEXT[span.start : span.end] == "Margaret Holloway"


def test_make_span_rejects_mismatched_text() -> None:
    with pytest.raises(AppError) as exc:
        make_span(
            id="t2",
            original_text=TEXT,
            start=5,
            end=22,
            type=PiiType.PERSON,
            confidence=0.9,
            source="manual",
            reason="wrong offsets",
            text="0412 887 905",  # does not match the slice
        )
    assert exc.value.error == "span_offset_mismatch"


def test_make_span_rejects_out_of_range() -> None:
    with pytest.raises(AppError) as exc:
        make_span(
            id="t3",
            original_text=TEXT,
            start=5,
            end=9999,
            type=PiiType.OTHER,
            confidence=0.1,
            source="regex",
            reason="oob",
        )
    assert exc.value.error == "span_offsets_out_of_range"


def test_session_init_starts_with_no_spans() -> None:
    resp = client.post("/api/session/init", json={"text": TEXT})
    assert resp.status_code == 200
    body = resp.json()
    assert body["original_text"] == TEXT
    assert body["spans"] == []
    assert body["output_mode"] == OutputMode.REDACT.value

    # And it can be fetched back by id.
    got = client.get(f"/api/session/{body['session_id']}")
    assert got.status_code == 200
    assert got.json()["session_id"] == body["session_id"]


def test_missing_session_returns_typed_error() -> None:
    resp = client.get("/api/session/does-not-exist")
    assert resp.status_code == 404
    assert resp.json()["error"] == "session_not_found"
