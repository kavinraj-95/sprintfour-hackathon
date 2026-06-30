"""Test gate for detection layer 2 (dictionary), run against the seeded fixture.

Two jobs, two assertions: the layer must (1) flag entities from a provided
closed-world list at the right offsets, and (2) mark the non-sensitive org as an
allowlist range for later layers to suppress.
"""
from __future__ import annotations

import json

import config
from models.contract import PiiType
from services.detection import dictionary_layer
from services.detection.dictionary_layer import KnownEntity

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))

# The closed world for THIS matter: the parties and identifiers a firm would
# already know going in. Offsets come from the labels oracle.
_KNOWN = [
    KnownEntity("Margaret Holloway", PiiType.PERSON),
    KnownEntity("Daniel Okafor", PiiType.PERSON),
    KnownEntity("CR-88341-AC", PiiType.ID_NUMBER),
]


def _label(span_id: str) -> dict:
    return next(s for s in _LABELS["spans"] if s["id"] == span_id)


def test_flags_known_list_entities_with_correct_offsets() -> None:
    result = dictionary_layer.detect(_SAMPLE, known_entities=_KNOWN)

    got = {(s.start, s.end, s.type.value) for s in result.spans}
    expected = {
        (_label("p1")["start"], _label("p1")["end"], "PERSON"),  # Margaret Holloway
        (_label("p3")["start"], _label("p3")["end"], "PERSON"),  # Daniel Okafor
        (_label("id1")["start"], _label("id1")["end"], "ID_NUMBER"),  # CR-88341-AC
    }
    assert got == expected, f"\n  missing: {expected - got}\n  extra: {got - expected}"

    for s in result.spans:
        assert s.source == "dictionary"
        assert s.confidence >= 0.95
        assert s.reason
        assert s.text == _SAMPLE[s.start : s.end]  # offset rule


def test_marks_non_sensitive_org_as_allowlisted() -> None:
    # Pass the org explicitly so the allowlist behaviour is asserted directly.
    result = dictionary_layer.detect(
        _SAMPLE, known_entities=_KNOWN, allowlist_terms=["Coastline Mutual"]
    )

    al = _LABELS["allowlist"][0]  # Coastline Mutual
    ranges = {(r.start, r.end) for r in result.allowlist}
    assert (al["start"], al["end"]) in ranges

    org = next(r for r in result.allowlist if r.start == al["start"])
    assert org.text == "Coastline Mutual"
    assert org.text == _SAMPLE[org.start : org.end]  # offset rule for allowlist too
    assert org.reason

    # The allowlisted org must NOT also be emitted as a (sensitive) span.
    assert all(s.text != "Coastline Mutual" for s in result.spans)


def test_default_allowlist_covers_the_fixture_org() -> None:
    # With no explicit allowlist, the built-in default still catches the org.
    result = dictionary_layer.detect(_SAMPLE, known_entities=_KNOWN)
    al = _LABELS["allowlist"][0]
    assert any(r.start == al["start"] and r.end == al["end"] for r in result.allowlist)


def test_only_provided_entities_are_flagged() -> None:
    result = dictionary_layer.detect(_SAMPLE, known_entities=_KNOWN)

    # Bare "Margaret" (p2) is a real occurrence but is NOT in the closed-world
    # list (only the full name is), so the dictionary layer must not flag it.
    # Linking the bare token to the full name is the consistency/merge layer's
    # job, not this one.
    p2 = _label("p2")
    assert all(
        not (s.start == p2["start"] and s.end == p2["end"]) for s in result.spans
    )

    # Nothing fires when the closed world is empty.
    empty = dictionary_layer.detect(_SAMPLE, known_entities=[], allowlist_terms=[])
    assert empty.spans == []
    assert empty.allowlist == []
