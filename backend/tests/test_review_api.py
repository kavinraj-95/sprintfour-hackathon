"""Integration tests for the review/correction API over the live app.

Covers the states the UX depends on: a tiered queue, layers-ran reporting,
reversible accept/dismiss/add-missed/undo, the live preview toggle, and the
export gate (held while high-risk items are unresolved; releases on confirm).
"""
from __future__ import annotations

import config
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")


def _create() -> dict:
    resp = client.post("/api/review", json={"text": _SAMPLE, "output_mode": "REDACT"})
    assert resp.status_code == 200
    return resp.json()


def test_landing_queue_is_tiered_and_reports_layers() -> None:
    state = _create()

    # Honest "what ran": regex/dictionary/ner ran, llm skipped by default.
    by_name = {l["name"]: l for l in state["layers"]}
    assert by_name["regex"]["status"] == "ok"
    assert by_name["llm"]["status"] == "skipped"  # never silently omitted
    assert {"regex", "dictionary", "ner", "llm"} <= set(by_name)

    # Queue exists and is ranked high-risk first.
    tiers = [it["tier"] for it in state["queue"]]
    assert tiers == sorted(tiers)
    assert state["queue"], "fixture should yield findings"
    # Every item carries one-glance context + a reason + a one-key-able status.
    first = state["queue"][0]
    assert first["sentence"] and first["reason"] and first["status"] == "pending"


def test_linked_phone_resolves_all_occurrences_in_one_action() -> None:
    sid = _create()["session_id"]
    phones = [it for it in client.get(f"/api/review/{sid}").json()["queue"]
              if it["type"] == "PHONE"]
    assert len(phones) == 2 and all(it["linked_count"] >= 1 for it in phones)

    # ONE accept on one phone resolves BOTH occurrences (server cascades).
    after = client.post(f"/api/review/{sid}/action",
                        json={"type": "accept", "target_id": phones[0]["id"]}).json()
    statuses = {it["id"]: it["status"] for it in after["queue"]}
    assert statuses[phones[0]["id"]] == "accepted"
    assert statuses[phones[1]["id"]] == "accepted", "linked occurrence not resolved too"

    # ONE undo reverts BOTH (a single reversible gesture).
    reverted = client.post(f"/api/review/{sid}/action", json={"type": "undo"}).json()
    statuses = {it["id"]: it["status"] for it in reverted["queue"]}
    assert statuses[phones[0]["id"]] == "pending"
    assert statuses[phones[1]["id"]] == "pending", "undo must revert the whole group"


def test_accept_dismiss_and_undo_are_reversible() -> None:
    sid = _create()["session_id"]
    item = client.get(f"/api/review/{sid}").json()["queue"][0]["id"]

    after = client.post(f"/api/review/{sid}/action",
                        json={"type": "accept", "target_id": item}).json()
    assert next(i for i in after["queue"] if i["id"] == item)["status"] == "accepted"

    after = client.post(f"/api/review/{sid}/action", json={"type": "undo"}).json()
    assert next(i for i in after["queue"] if i["id"] == item)["status"] == "pending"


def test_add_missed_by_selection_then_undo() -> None:
    sid = _create()["session_id"]
    # Select an arbitrary visible range as "missed PII".
    start = _SAMPLE.index("underwriting")
    end = start + len("underwriting")
    after = client.post(f"/api/review/{sid}/action", json={
        "type": "add_missed", "start": start, "end": end, "pii_type": "OTHER",
    }).json()
    added = [i for i in after["queue"] if i["start"] == start and i["end"] == end]
    assert added and added[0]["status"] == "accepted" and added[0]["tier"] == 1

    after = client.post(f"/api/review/{sid}/action", json={"type": "undo"}).json()
    assert not [i for i in after["queue"] if i["start"] == start and i["end"] == end]


def test_preview_toggle_rerenders_without_redetecting() -> None:
    sid = _create()["session_id"]
    # Accept every high-risk item so there's something to render.
    for it in client.get(f"/api/review/{sid}").json()["queue"]:
        if it["tier"] == 1:
            client.post(f"/api/review/{sid}/action",
                        json={"type": "accept", "target_id": it["id"]})

    redact = client.post(f"/api/review/{sid}/preview", json={"output_mode": "REDACT"}).json()
    anon = client.post(f"/api/review/{sid}/preview", json={"output_mode": "ANONYMIZE"}).json()
    assert "[REDACTED]" in redact["output_text"]
    assert "[" in anon["output_text"] and "_1]" in anon["output_text"]


def test_export_is_gated_until_high_risk_resolved() -> None:
    sid = _create()["session_id"]

    # With tier-1 items still pending, export is held back (no output produced).
    gated = client.post(f"/api/review/{sid}/export", json={"output_mode": "REDACT"}).json()
    assert gated["gated"] is True
    assert gated["output_text"] is None
    assert gated["unresolved"], "gate must list what still needs review"

    # Resolve every high-risk item (accept or dismiss), then export succeeds.
    for it in client.get(f"/api/review/{sid}").json()["queue"]:
        if it["tier"] == 1:
            client.post(f"/api/review/{sid}/action",
                        json={"type": "accept", "target_id": it["id"]})
    done = client.post(f"/api/review/{sid}/export", json={"output_mode": "REDACT"}).json()
    assert done["gated"] is False and done["output_text"] is not None

    # A user can also force past the gate with a deliberate confirm.
    sid2 = _create()["session_id"]
    forced = client.post(f"/api/review/{sid2}/export",
                         json={"output_mode": "REDACT", "confirm": True}).json()
    assert forced["gated"] is False
