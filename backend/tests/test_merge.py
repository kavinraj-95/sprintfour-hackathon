"""Test gate for the merge/differentiation step (layer 5), over the fixture.

Asserts the behaviours the review queue depends on: linked phone duplicates,
both name occurrences kept (bare one not dropped), the relational name as a
tier-3 soft review, and the allowlisted org suppressed entirely.
"""
from __future__ import annotations

import json

import config
from models.contract import PiiType
from services.detection.dictionary_layer import AllowlistRange
from services.detection.merge import RiskTier, merge
from services.spans import make_span

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))


def _lab(span_id: str) -> dict:
    return next(s for s in _LABELS["spans"] + _LABELS["allowlist"] if s["id"] == span_id)


def _span(lab_id: str, type: PiiType, source, conf: float, normalized=None, reason="x"):
    lab = _lab(lab_id)
    return make_span(
        id=f"{source}:{lab_id}", original_text=_SAMPLE,
        start=lab["start"], end=lab["end"], type=type, confidence=conf,
        source=source, reason=reason, normalized_value=normalized,
    )


def _candidates():
    """A realistic cross-layer candidate set anchored to the fixture.

    Margaret Holloway = dictionary + ner (structural agreement). The two phone
    formats = regex, with DIFFERENT digits-only normalized values (must still
    link). Daniel Okafor = llm-only (the relational catch). Coastline Mutual =
    an ner false positive inside the allowlist (must be suppressed).
    """
    return [
        _span("p1", PiiType.PERSON, "dictionary", 0.98),
        _span("p1", PiiType.PERSON, "ner", 0.85),          # overlaps -> coalesce
        _span("ph1", PiiType.PHONE, "regex", 0.99, normalized="0412887905"),
        _span("ph2", PiiType.PHONE, "regex", 0.99, normalized="61412887905"),
        _span("em1", PiiType.EMAIL, "regex", 0.99, normalized="margaret.holloway@fastmail.com"),
        _span("p2", PiiType.PERSON, "ner", 0.85),          # bare "Margaret"
        _span("p3", PiiType.PERSON, "llm", 0.55),          # relational, llm-only
        _span("al1", PiiType.ORG, "ner", 0.80),            # Coastline Mutual (allowlisted)
    ]


_ALLOWLIST = [AllowlistRange(start=a["start"], end=a["end"], text=a["text"], reason="x")
              for a in _LABELS["allowlist"]]


def _at(merged, lab_id):
    lab = _lab(lab_id)
    return next((m for m in merged if m.start < lab["end"] and lab["start"] < m.end), None)


def test_both_phone_occurrences_are_linked() -> None:
    merged = merge(_candidates(), allowlist=_ALLOWLIST)
    ph1, ph2 = _at(merged, "ph1"), _at(merged, "ph2")
    assert ph1 and ph2
    # Each references the other as a linked occurrence (despite differing digits).
    assert any(o.start == ph2.start for o in ph1.linked)
    assert any(o.start == ph1.start for o in ph2.linked)
    assert ph1.tier is RiskTier.HIGH and ph2.tier is RiskTier.HIGH


def test_both_name_occurrences_present_bare_not_dropped() -> None:
    merged = merge(_candidates(), allowlist=_ALLOWLIST)
    full, bare = _at(merged, "p1"), _at(merged, "p2")
    assert full is not None, "full name dropped"
    assert bare is not None, "bare 'Margaret' dropped"
    # Full name has structural agreement (dictionary+ner) -> high; sources unioned.
    assert full.tier is RiskTier.HIGH
    assert set(full.sources) == {"dictionary", "ner"}


def test_relational_name_is_tier3_soft() -> None:
    merged = merge(_candidates(), allowlist=_ALLOWLIST)
    daniel = _at(merged, "p3")
    assert daniel is not None
    assert daniel.sources == ["llm"]
    assert daniel.tier is RiskTier.SOFT_REVIEW


def test_allowlisted_org_absent_from_final_list() -> None:
    merged = merge(_candidates(), allowlist=_ALLOWLIST)
    al = _LABELS["allowlist"][0]
    assert all(not (m.start < al["end"] and al["start"] < m.end) for m in merged)


def test_output_is_ranked_high_risk_first() -> None:
    merged = merge(_candidates(), allowlist=_ALLOWLIST)
    tiers = [m.tier for m in merged]
    assert tiers == sorted(tiers), "queue must be ordered by tier (high risk first)"
