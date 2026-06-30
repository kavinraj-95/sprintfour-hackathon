"""Layer 5: merge / differentiation — one pure function, one ranked list.

Every earlier layer (regex, dictionary, ner, llm) produces candidate spans
independently. This step reconciles them into a single, de-duplicated, ranked
list per the `pii-contract` precedence table, and assigns the risk tier that
drives BOTH the merge ordering and the UI review queue (one vocabulary).

Precedence (see pii-contract):
  1. regex + dictionary are near-certain -> win ties.
  2. ner vs llm disagree on the same span -> llm decides (it had sentence context).
  3. llm-only catch with no structural backup -> kept, but lower severity (tier 3).
  4. Coalesce OVERLAPPING spans: union sources, keep max confidence, merge reasons.
  5. Link DUPLICATES: same canonical value at different spots -> tied together so
     the UI can fix all at once (record the other occurrences' offsets).
  6. Anything inside a dictionary ALLOWLIST range is suppressed.

Coalesce vs link are different: coalesce merges spans at the SAME place (several
layers found one thing); link ties spans at DIFFERENT places (one value, many
occurrences). Phones are canonicalised before linking so two formats of one
number link (the digits-only forms differ — that is the documented adversarial
case).
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from enum import IntEnum

from pydantic import BaseModel, Field

from models.contract import PiiType, Span, SpanSource

_STRUCTURAL: frozenset[SpanSource] = frozenset({"regex", "dictionary"})
_NON_DIGITS = re.compile(r"\D")


class RiskTier(IntEnum):
    """Ordering vocabulary shared by the merge output and the UI queue."""

    HIGH = 1            # structural agreement on sensitive PII, or any linked duplicate
    LOW_CONFIDENCE = 2  # flagged but uncertain (e.g. lone NER catch)
    SOFT_REVIEW = 3     # llm-only, no structural backup — dismissible


class OccurrenceRef(BaseModel):
    start: int
    end: int


class MergedSpan(BaseModel):
    """One reconciled finding. Carries everything the queue needs to rank and
    explain it; the review layer adds the user's decision + sentence context."""

    id: str
    start: int
    end: int
    text: str
    type: PiiType
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[SpanSource]              # union of every layer that found it
    reason: str                            # merged 'why', one line per source
    normalized_value: str | None = None
    tier: RiskTier
    linked: list[OccurrenceRef] = Field(default_factory=list)  # OTHER occurrences


# An allowlist range is anything with .start/.end (dictionary_layer.AllowlistRange);
# typed structurally to avoid coupling the merge step to the dictionary layer.
class _HasRange:  # pragma: no cover - typing aid only
    start: int
    end: int


def _canonical_phone(value: str) -> str:
    """National subscriber number, so '0412…' and '+61 412…' link. AU-centric
    simplification (documented); production would use libphonenumber."""
    digits = _NON_DIGITS.sub("", value)
    if digits.startswith("0"):
        return digits[1:]
    if digits.startswith("61"):
        return digits[2:]
    return digits


def _link_key(type: PiiType, normalized_value: str | None, text: str) -> str | None:
    """The value identity used to link duplicate occurrences. None => never link
    (e.g. names, which differ token-to-token and are not duplicate-linked here)."""
    if type is PiiType.PHONE and normalized_value:
        return f"PHONE:{_canonical_phone(normalized_value)}"
    if normalized_value:
        return f"{type.value}:{normalized_value}"
    return None


def _coalesce_groups(spans: list[Span]) -> list[list[Span]]:
    """Group spans into overlapping clusters via a sorted interval sweep."""
    groups: list[list[Span]] = []
    cluster_end = -1
    for span in sorted(spans, key=lambda s: (s.start, s.end)):
        if groups and span.start < cluster_end:  # overlaps the current cluster
            groups[-1].append(span)
            cluster_end = max(cluster_end, span.end)
        else:
            groups.append([span])
            cluster_end = span.end
    return groups


def _winner(group: list[Span]) -> Span:
    """Resolve which candidate's type/offsets stand, per precedence 1 then 2."""
    structural = [s for s in group if s.source in _STRUCTURAL]
    if structural:
        return max(structural, key=lambda s: s.confidence)         # rule 1
    llm = [s for s in group if s.source == "llm"]
    if llm:
        return max(llm, key=lambda s: s.confidence)                # rule 2
    return max(group, key=lambda s: s.confidence)


def _assign_tier(sources: set[SpanSource], linked: bool) -> RiskTier:
    if linked or (sources & _STRUCTURAL):
        return RiskTier.HIGH
    if sources == {"llm"}:
        return RiskTier.SOFT_REVIEW
    return RiskTier.LOW_CONFIDENCE


def merge(candidates: Sequence[Span], *, allowlist: Sequence[_HasRange] = ()) -> list[MergedSpan]:
    """Reconcile all candidate spans into one ranked, de-duplicated list. Pure."""
    # Rule 6: suppress anything inside an allowlist range.
    kept = [
        c for c in candidates
        if not any(c.start < a.end and a.start < c.end for a in allowlist)
    ]

    # Rule 4: coalesce overlapping candidates into one finding each.
    coalesced: list[dict] = []
    for group in _coalesce_groups(kept):
        win = _winner(group)
        sources = sorted({s.source for s in group})
        reasons = list(dict.fromkeys(f"[{s.source}] {s.reason}" for s in group))
        normalized = next((s.normalized_value for s in group if s.normalized_value), None)
        coalesced.append({
            "start": win.start, "end": win.end, "text": win.text, "type": win.type,
            "confidence": max(s.confidence for s in group),
            "sources": sources, "reason": " | ".join(reasons),
            "normalized_value": normalized,
        })

    # Rule 5: link duplicates by canonical value.
    by_key: dict[str, list[int]] = {}
    for i, c in enumerate(coalesced):
        key = _link_key(c["type"], c["normalized_value"], c["text"])
        if key is not None:
            by_key.setdefault(key, []).append(i)

    merged: list[MergedSpan] = []
    for i, c in enumerate(coalesced):
        key = _link_key(c["type"], c["normalized_value"], c["text"])
        group_idx = by_key.get(key, [i]) if key else [i]
        linked = [
            OccurrenceRef(start=coalesced[j]["start"], end=coalesced[j]["end"])
            for j in group_idx if j != i
        ]
        tier = _assign_tier(set(c["sources"]), linked=bool(linked))
        merged.append(MergedSpan(
            id=f"m:{c['start']}-{c['end']}",
            tier=tier, linked=linked, **c,
        ))

    # Ranked output: highest risk first, then document order.
    merged.sort(key=lambda m: (m.tier, m.start))
    return merged
