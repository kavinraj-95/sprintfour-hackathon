"""Test gate for detection layer 3 (NER, Presidio-based), over the seeded fixture.

NER must recover the contextual PII the earlier layers cannot: both occurrences
of the claimant's name, the no-anchor supervisor name, and the full street
address — while respecting the dictionary allowlist (the public org name that
Presidio mislabels as a person must NOT be emitted).

Assertions are overlap-based: a statistical model's boundaries won't match the
hand-labelled offsets exactly, so "found" means "a same-type span overlaps the
ground-truth range".
"""
from __future__ import annotations

import json

import config
from models.contract import PiiType
from services.detection import ner_layer
from services.detection.dictionary_layer import AllowlistRange

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))

# The allowlist the dictionary layer would hand to NER for this document.
_ALLOWLIST = [
    AllowlistRange(start=a["start"], end=a["end"], text=a["text"], reason="test")
    for a in _LABELS["allowlist"]
]


def _label(span_id: str) -> dict:
    return next(s for s in _LABELS["spans"] if s["id"] == span_id)


def _overlaps(span, start: int, end: int) -> bool:
    return span.start < end and start < span.end


def _found(spans, label: dict, pii_type: PiiType) -> bool:
    return any(
        s.type == pii_type and _overlaps(s, label["start"], label["end"]) for s in spans
    )


def test_ner_finds_both_name_occurrences_and_the_no_anchor_name() -> None:
    spans = ner_layer.detect(_SAMPLE, allowlist=_ALLOWLIST)
    assert _found(spans, _label("p1"), PiiType.PERSON), "missed 'Margaret Holloway'"
    assert _found(spans, _label("p2"), PiiType.PERSON), "missed bare 'Margaret' (2nd occ)"
    assert _found(spans, _label("p3"), PiiType.PERSON), "missed no-anchor 'Daniel Okafor'"


def test_ner_finds_the_street_address() -> None:
    spans = ner_layer.detect(_SAMPLE, allowlist=_ALLOWLIST)
    assert _found(spans, _label("ad1"), PiiType.ADDRESS), "missed the street address"


def test_ner_respects_the_allowlist() -> None:
    org = _LABELS["allowlist"][0]  # Coastline Mutual

    # With the allowlist, nothing may overlap the org's range.
    spans = ner_layer.detect(_SAMPLE, allowlist=_ALLOWLIST)
    assert all(not _overlaps(s, org["start"], org["end"]) for s in spans), (
        "allowlisted org leaked into NER output"
    )

    # Sanity: without the allowlist, Presidio DOES flag it — proving the
    # suppression above is doing real work, not passing vacuously.
    raw = ner_layer.detect(_SAMPLE, allowlist=[])
    assert any(_overlaps(s, org["start"], org["end"]) for s in raw), (
        "expected raw Presidio to flag the org (benchmark says it mislabels it PERSON)"
    )


def test_every_ner_span_obeys_contract_and_calibration() -> None:
    for s in ner_layer.detect(_SAMPLE, allowlist=_ALLOWLIST):
        assert s.text == _SAMPLE[s.start : s.end]  # offset rule
        assert s.source == "ner"
        assert 0.0 < s.confidence < 0.98  # below the regex/dictionary band
        assert s.reason
        assert s.type in {PiiType.PERSON, PiiType.ORG, PiiType.ADDRESS}
