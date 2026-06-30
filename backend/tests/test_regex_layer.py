"""Test gate for detection layer 1 (regex), run against the seeded fixture.

The oracle is fixtures/labels.json: the regex layer must recover exactly the
structured-PII spans (PHONE / EMAIL / ID_NUMBER) with correct offsets, and must
NOT emit any PERSON or ORG span — names and organisations are not regex's job.
"""
from __future__ import annotations

import json
from pathlib import Path

import config
from models.contract import PiiType
from services.detection import regex_layer

# Types this layer is responsible for. Everything else (PERSON, ORG, ADDRESS)
# belongs to a later layer and must be left untouched here.
_STRUCTURED_TYPES = {"PHONE", "EMAIL", "ID_NUMBER"}

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))


def _expected_structured() -> list[dict]:
    return [s for s in _LABELS["spans"] if s["type"] in _STRUCTURED_TYPES]


def test_regex_recovers_every_structured_span_with_correct_offsets() -> None:
    spans = regex_layer.detect(_SAMPLE)

    got = {(s.start, s.end, s.type.value) for s in spans}
    expected = {(s["start"], s["end"], s["type"]) for s in _expected_structured()}

    # Exact match: no misses (every structured label found) and no extras
    # (no names, orgs, addresses, or spurious shapes).
    assert got == expected, (
        f"\n  missing: {expected - got}\n  unexpected: {got - expected}"
    )


def test_every_span_obeys_the_offset_rule_and_layer_metadata() -> None:
    for s in regex_layer.detect(_SAMPLE):
        assert s.text == _SAMPLE[s.start : s.end]
        assert s.source == "regex"
        assert s.confidence >= 0.95
        assert s.reason  # every candidate names its pattern
        assert s.type in {PiiType.PHONE, PiiType.EMAIL, PiiType.ID_NUMBER}


def test_finds_no_names_or_org_names() -> None:
    spans = regex_layer.detect(_SAMPLE)

    # No emitted type is a name/org...
    assert all(s.type not in {PiiType.PERSON, PiiType.ORG} for s in spans)

    # ...and no emitted span overlaps a PERSON or ORG ground-truth range, so we
    # are not silently mislabelling a name as, say, an ID.
    name_org_ranges = [
        (e["start"], e["end"])
        for e in _LABELS["spans"] + _LABELS["allowlist"]
        if e["type"] in {"PERSON", "ORG"}
    ]
    for s in spans:
        for a, b in name_org_ranges:
            assert not (s.start < b and a < s.end), (
                f"regex span {s.text!r} overlaps a name/org range [{a},{b})"
            )


def test_phone_and_email_record_normalized_value() -> None:
    by_text = {s.text: s for s in regex_layer.detect(_SAMPLE)}

    # Phones: digits-only (the two formats normalise differently here, by design
    # — cross-format linking is a merge-step concern, see labels.json).
    assert by_text["0412 887 905"].normalized_value == "0412887905"
    assert by_text["+61 412 887 905"].normalized_value == "61412887905"

    # Email: lowercased (already lower here, but the rule is applied).
    assert (
        by_text["margaret.holloway@fastmail.com"].normalized_value
        == "margaret.holloway@fastmail.com"
    )


def test_address_is_not_claimed_by_regex() -> None:
    # The street address is real PII, but it has no high-precision regex shape,
    # so this layer must leave it for a later layer rather than guess.
    addr = next(s for s in _LABELS["spans"] if s["type"] == "ADDRESS")
    for s in regex_layer.detect(_SAMPLE):
        assert not (s.start < addr["end"] and addr["start"] < s.end)


def test_luhn_account_number_detected_and_non_luhn_ignored() -> None:
    # 4111 1111 1111 1111 is a Luhn-valid test card number.
    valid = "Charge applied to card 4111 1111 1111 1111 on file."
    spans = regex_layer.detect(valid)
    assert any(
        s.type == PiiType.ID_NUMBER and s.text == "4111 1111 1111 1111" for s in spans
    ), "Luhn-valid account number should be detected as ID_NUMBER"

    # Same shape, one digit changed so the checksum fails -> not flagged.
    invalid = "Charge applied to card 4111 1111 1111 1112 on file."
    assert not any(s.type == PiiType.ID_NUMBER for s in regex_layer.detect(invalid)), (
        "a non-Luhn 16-digit run must not be flagged as an account number"
    )
