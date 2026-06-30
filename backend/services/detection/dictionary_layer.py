"""Layer 2 of the detection pipeline: closed-world dictionary / gazetteer.

Per `layer-discipline`, this layer reasons only about a *known world*. It does
two distinct jobs, and they pull in opposite directions on purpose:

1. KNOWN ENTITIES -> spans. Given a provided closed-world list (the parties and
   identifiers known for THIS matter — case IDs, claimant/party names), it finds
   every occurrence and emits a Span with source="dictionary". Exact matches
   against a curated list are near-certain, so confidence is high.

2. ALLOWLIST -> suppression ranges. A set of strings that *look* like PII but are
   not sensitive here (the underwriter's public name, court/registry names, ...).
   This layer does NOT match these as PII; it produces a list of ranges so that
   LATER layers (NER, LLM, merge) suppress anything inside them. That is the
   only thing standing between a generic NER model and a wall of false positives
   on public org names.

The known-entity list is injected (it is specific to the case in hand). The
allowlist has a built-in default of globally-safe terms and can be extended.

This layer only reports the allowlist ranges; it does not apply suppression to
other layers' output — that is the merge step's job (see `pii-contract`).
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from models.contract import PiiType, Span
from services.spans import make_span

# Closed-world exact matches are about as certain as regex. Kept just below 1.0
# for the same reason regex is: a curated list can still contain a mistake.
_DICTIONARY_CONFIDENCE = 0.98


@dataclass(frozen=True)
class KnownEntity:
    """One entry in the closed-world list: a literal string and what it is."""

    text: str
    type: PiiType


@dataclass(frozen=True)
class AllowlistRange:
    """A [start, end) range that later layers must treat as non-sensitive.

    Not a Span: an allowlisted string is explicitly NOT PII, so it carries no
    PiiType. It exists to be subtracted from later layers' candidates.
    """

    start: int
    end: int
    text: str
    reason: str


@dataclass(frozen=True)
class DictionaryResult:
    """The layer's two outputs, kept separate by intent."""

    spans: list[Span] = field(default_factory=list)
    allowlist: list[AllowlistRange] = field(default_factory=list)


# Globally-safe, PII-shaped strings. The underwriter from the fixture plus a few
# representative court/registry names — the kind of public entity a name-based
# detector would otherwise flag. Extend per deployment; injectable for tests.
DEFAULT_ALLOWLIST_TERMS: tuple[str, ...] = (
    "Coastline Mutual",
    "Supreme Court of New South Wales",
    "District Court of New South Wales",
    "Federal Court of Australia",
)


def _find_all(text: str, term: str) -> Iterable[tuple[int, int]]:
    """Yield (start, end) of every whole-word, case-insensitive match of `term`.

    Whole-word boundaries stop 'Mutual' from matching inside 'Mutuality' and the
    like; case-insensitive so a known name still matches if the document's
    casing differs. Offsets index the document, so the real cased slice is kept.
    """
    if not term:
        return
    pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
    for m in pattern.finditer(text):
        yield m.start(), m.end()


def detect(
    original_text: str,
    *,
    known_entities: Sequence[KnownEntity] = (),
    allowlist_terms: Sequence[str] = DEFAULT_ALLOWLIST_TERMS,
) -> DictionaryResult:
    """Run the dictionary layer. Pure: same inputs -> same result.

    Returns spans for known entities and a separate list of allowlist ranges.
    """
    spans: list[Span] = []
    for entity in known_entities:
        for start, end in _find_all(original_text, entity.text):
            spans.append(
                make_span(
                    id=f"dict:{start}-{end}",
                    original_text=original_text,
                    start=start,
                    end=end,
                    type=entity.type,
                    confidence=_DICTIONARY_CONFIDENCE,
                    source="dictionary",
                    reason=(
                        f"exact match against the closed-world "
                        f"{entity.type.value} list"
                    ),
                )
            )

    allowlist: list[AllowlistRange] = []
    for term in allowlist_terms:
        for start, end in _find_all(original_text, term):
            # Offset rule holds by construction: text is taken from the slice,
            # and `_find_all` only yields in-range match positions.
            allowlist.append(
                AllowlistRange(
                    start=start,
                    end=end,
                    text=original_text[start:end],
                    reason="known non-sensitive entity on the dictionary allowlist",
                )
            )

    spans.sort(key=lambda s: s.start)
    allowlist.sort(key=lambda r: r.start)
    return DictionaryResult(spans=spans, allowlist=allowlist)
