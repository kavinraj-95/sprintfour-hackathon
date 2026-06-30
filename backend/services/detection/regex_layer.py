"""Layer 1 of the detection pipeline: high-precision regex over structured PII.

Per `layer-discipline`, this is the cheapest, most certain layer. It claims only
the shapes that can be matched deterministically with near-perfect precision:

    PHONE       phone-number shapes
    EMAIL       email addresses
    ID_NUMBER   US SSNs, Luhn-valid account/card numbers, alphanumeric ref codes

It deliberately does NOT attempt PERSON, ORG, or ADDRESS. Those have no reliable
surface form — a name or street is just words — so trying to regex them trades
precision for recall and pollutes the pool the later layers reason over. Names
and orgs are the dictionary / NER / LLM layers' job; this layer leaves them be.

Every hit becomes a Span with source="regex", confidence near (but not exactly)
1.0, and a `reason` naming the pattern that fired. Phones and emails also record
a `normalized_value` so the later merge step can link duplicate occurrences.

This layer RECORDS the normalized value; it does NOT link. Note the deliberate
choice of *digits-only* for phones: '0412 887 905' -> '0412887905' and
'+61 412 887 905' -> '61412887905' do NOT match, so digits-only alone will not
link those two. That is the `duplicate-phone-two-formats` adversarial case in
fixtures/labels.json — canonicalising the two formats to one value is a merge-
step concern, kept out of this layer on purpose.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from models.contract import PiiType, Span
from services.spans import make_span

# Near-certain, but not infallible: we leave a sliver below 1.0 so that a later
# layer with real surrounding context could in principle overturn an obvious
# false positive. Regex is precise, not omniscient.
_REGEX_CONFIDENCE = 0.99

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# A phone-shaped run: optional '+', then digits/spaces/()-./ , bounded so it must
# start and end on a digit. The strict digit-count check below is what gives it
# precision — the pattern only finds candidates.
_PHONE_RE = re.compile(r"\+?\d[\d\s().\-]{7,}\d")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# A long digit run (13–19 digits, spaces/hyphens allowed) — an account/card-number
# *candidate*; only kept if it passes the Luhn checksum.
_ACCOUNT_RE = re.compile(r"\b\d[\d \-]{11,21}\d\b")
# An UPPERCASE alphanumeric code joined by hyphens (e.g. a claim/policy ref,
# CR-88341-AC). Kept only when it contains BOTH a letter and a digit, which
# excludes plain words and bare numbers.
_REFERENCE_RE = re.compile(r"\b[A-Z0-9]+(?:-[A-Z0-9]+)+\b")

_DIGITS = re.compile(r"\D")


def _digits_only(s: str) -> str:
    return _DIGITS.sub("", s)


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn checksum. Only meaningful for card/account-length numbers."""
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    type: PiiType
    reason: str
    normalized_value: str | None
    priority: int  # lower = more authoritative; wins overlaps


def _candidates(text: str) -> list[_Candidate]:
    """Run every pattern and collect raw candidates (pre-overlap-resolution).

    Priority order encodes which shape wins when two patterns claim the same
    span: the more specific structured shapes outrank the looser reference code.
    """
    out: list[_Candidate] = []

    for m in _EMAIL_RE.finditer(text):
        out.append(_Candidate(m.start(), m.end(), PiiType.EMAIL,
                               "email-address pattern", m.group().lower(), 0))

    for m in _PHONE_RE.finditer(text):
        digits = _digits_only(m.group())
        if 9 <= len(digits) <= 15:  # E.164 caps national numbers at 15 digits
            out.append(_Candidate(m.start(), m.end(), PiiType.PHONE,
                                  "phone-number pattern", digits, 1))

    for m in _SSN_RE.finditer(text):
        out.append(_Candidate(m.start(), m.end(), PiiType.ID_NUMBER,
                               "US SSN pattern (NNN-NN-NNNN)", None, 2))

    for m in _ACCOUNT_RE.finditer(text):
        digits = _digits_only(m.group())
        if _luhn_ok(digits):
            out.append(_Candidate(m.start(), m.end(), PiiType.ID_NUMBER,
                                  "Luhn-valid account/card number", digits, 2))

    for m in _REFERENCE_RE.finditer(text):
        token = m.group()
        if any(c.isalpha() for c in token) and any(c.isdigit() for c in token):
            out.append(_Candidate(m.start(), m.end(), PiiType.ID_NUMBER,
                                  "alphanumeric reference/ID code", None, 3))

    return out


def _resolve_overlaps(candidates: list[_Candidate]) -> list[_Candidate]:
    """Keep non-overlapping candidates, preferring higher priority then longer.

    Two patterns rarely claim the same span, but if they do (e.g. a Luhn number
    that also looks phone-ish) we keep one rather than emit duplicates.
    """
    ordered = sorted(candidates, key=lambda c: (c.priority, -(c.end - c.start), c.start))
    kept: list[_Candidate] = []
    for cand in ordered:
        if any(cand.start < k.end and k.start < cand.end for k in kept):
            continue
        kept.append(cand)
    return sorted(kept, key=lambda c: c.start)


def detect(original_text: str) -> list[Span]:
    """Detect structured PII in `original_text`. Returns spans ordered by start.

    The single entry point for this layer. Pure: same text in, same spans out.
    """
    resolved = _resolve_overlaps(_candidates(original_text))
    return [
        make_span(
            id=f"regex:{c.start}-{c.end}",
            original_text=original_text,
            start=c.start,
            end=c.end,
            type=c.type,
            confidence=_REGEX_CONFIDENCE,
            source="regex",
            reason=c.reason,
            normalized_value=c.normalized_value,
        )
        for c in resolved
    ]
