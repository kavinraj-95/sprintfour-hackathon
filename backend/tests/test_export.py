"""Tests for the output stage (REDACT / ANONYMIZE) via POST /api/export.

Exercised through the endpoint so the server-side, authoritative behaviour is
what's tested: the output is rendered from the SUBMITTED accepted-span set.
"""
from __future__ import annotations

import json

import config
from fastapi.testclient import TestClient

from app import app
from models.contract import OutputMode, PiiType
from services.session_store import store
from services.spans import make_span

client = TestClient(app)

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))


def _label(span_id: str) -> dict:
    return next(s for s in _LABELS["spans"] if s["id"] == span_id)


def _seed_session() -> tuple[str, dict[str, str]]:
    """Create a session and attach accepted spans (as a reviewed set would be).

    Returns (session_id, {alias: span_id}). Phones carry digits-only
    normalized_value, deliberately DIFFERENT for the two formats, to prove the
    output stage canonicalises them to one token.
    """
    state = store.create(original_text=_SAMPLE, output_mode=OutputMode.REDACT)
    spec = [
        ("mh", _label("p1"), PiiType.PERSON, None),                 # Margaret Holloway
        ("id", _label("id1"), PiiType.ID_NUMBER, None),             # CR-88341-AC
        ("ph1", _label("ph1"), PiiType.PHONE, "0412887905"),        # 0412 887 905
        ("ph2", _label("ph2"), PiiType.PHONE, "61412887905"),       # +61 412 887 905
        ("em", _label("em1"), PiiType.EMAIL, "margaret.holloway@fastmail.com"),
        ("mb", _label("p2"), PiiType.PERSON, None),                 # bare "Margaret"
    ]
    ids: dict[str, str] = {}
    for alias, lab, typ, norm in spec:
        span = make_span(
            id=f"s_{alias}",
            original_text=_SAMPLE,
            start=lab["start"],
            end=lab["end"],
            type=typ,
            confidence=0.99,
            source="manual",
            reason="accepted by reviewer",
            normalized_value=norm,
        )
        state.spans.append(span)
        ids[alias] = span.id
    return state.session_id, ids


def _export(session_id: str, accepted_ids: list[str], mode: str):
    resp = client.post(
        "/api/export",
        json={"session_id": session_id, "accepted_span_ids": accepted_ids, "output_mode": mode},
    )
    return resp


# ---------------------------------------------------------------- REDACT ----
def test_redact_removes_pii_and_preserves_context() -> None:
    sid, ids = _seed_session()
    resp = _export(sid, list(ids.values()), "REDACT")
    assert resp.status_code == 200
    out = resp.json()["output_text"]

    # Every accepted value is structurally GONE from the output.
    for gone in [
        "Margaret Holloway",
        "Margaret",            # also covers the bare second occurrence
        "margaret.holloway@fastmail.com",
        "0412 887 905",
        "+61 412 887 905",
        "CR-88341-AC",
    ]:
        assert gone not in out, f"redacted value leaked into output: {gone!r}"

    # Non-PII context survives untouched.
    for kept in ["Claim reference:", "underwriting partner", "Hard-copy documents"]:
        assert kept in out, f"context was lost: {kept!r}"

    assert "[REDACTED]" in out


def test_redact_is_authoritative_to_submitted_set() -> None:
    # Only the two phones are accepted -> only they are removed; the rest stays.
    sid, ids = _seed_session()
    out = _export(sid, [ids["ph1"], ids["ph2"]], "REDACT").json()["output_text"]
    assert "0412 887 905" not in out and "+61 412 887 905" not in out
    assert "Margaret Holloway" in out  # not in the accepted set -> still present
    assert "margaret.holloway@fastmail.com" in out


# ------------------------------------------------------------- ANONYMIZE ----
def test_anonymize_uses_stable_type_aware_tokens() -> None:
    sid, ids = _seed_session()
    resp = _export(sid, list(ids.values()), "ANONYMIZE")
    assert resp.status_code == 200
    out = resp.json()["output_text"]

    # Raw values replaced.
    for gone in ["Margaret Holloway", "0412 887 905", "+61 412 887 905",
                 "margaret.holloway@fastmail.com", "CR-88341-AC"]:
        assert gone not in out

    # SAME entity -> SAME token: the one phone number, written two ways, gets a
    # single token at BOTH occurrences.
    assert out.count("[PHONE_1]") == 2
    assert "[PHONE_2]" not in out

    # Distinct entities of the same type get distinct numbers.
    assert "[PERSON_1]" in out and "[PERSON_2]" in out
    assert "[EMAIL_1]" in out and "[ID_NUMBER_1]" in out


def test_anonymize_legend_describes_entities_without_raw_pii() -> None:
    sid, ids = _seed_session()
    legend = _export(sid, list(ids.values()), "ANONYMIZE").json()["legend"]
    by_token = {e["token"]: e for e in legend}

    assert by_token["[PHONE_1]"]["type"] == "PHONE"
    assert by_token["[PHONE_1]"]["occurrences"] == 2          # linked across formats
    assert by_token["[PERSON_1]"]["occurrences"] == 1
    assert by_token["[PERSON_2]"]["type"] == "PERSON"

    # The legend is shareable: it must not carry the sensitive values.
    blob = json.dumps(legend)
    for raw in ["Margaret", "0412", "fastmail", "88341"]:
        assert raw not in blob


# ----------------------------------------------------------- error paths ----
def test_unknown_span_id_is_a_typed_400() -> None:
    sid, _ = _seed_session()
    resp = _export(sid, ["does-not-exist"], "REDACT")
    assert resp.status_code == 400
    assert resp.json()["error"] == "unknown_span_id"


def test_overlapping_accepted_spans_is_a_typed_400() -> None:
    state = store.create(original_text=_SAMPLE, output_mode=OutputMode.REDACT)
    a = make_span(id="a", original_text=_SAMPLE, start=48, end=65, type=PiiType.PERSON,
                  confidence=0.9, source="manual", reason="x")
    b = make_span(id="b", original_text=_SAMPLE, start=56, end=70, type=PiiType.PERSON,
                  confidence=0.9, source="manual", reason="x")
    state.spans.extend([a, b])
    resp = _export(state.session_id, ["a", "b"], "REDACT")
    assert resp.status_code == 400
    assert resp.json()["error"] == "overlapping_accepted_spans"
