"""The shared contract — the single source of truth for the data model.

This module is mirrored, field-for-field, by the frontend in
`frontend/src/types/contract.ts`. If you change a type here, change it there.
Keeping the two in lockstep is deliberate: the typed seam between client and
server is what lets every later layer (detection, finder, redaction) evolve
without breaking the wire format.

============================ THE OFFSET RULE ============================
A Span addresses a slice of `SessionState.original_text` by `[start, end)`,
where `start` and `end` are **Python codepoint indices** (i.e. indices into
the `str`, NOT UTF-8/UTF-16 byte or unit offsets). `end` is exclusive.

The invariant, true for EVERY span, everywhere one is created:

    span.text == original_text[span.start:span.end]

Codepoint indices are chosen because Python `str` slicing and JavaScript
string indexing over the same text can diverge for astral characters
(emoji, some CJK); we pin the contract to codepoints and the frontend
mirrors with `Array.from(text)` indexing when it must. Spans are never
constructed ad hoc — they go through `services.spans.make_span`, which
asserts this rule and raises a typed error if it is ever violated.
========================================================================
"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class PiiType(str, Enum):
    """The kinds of sensitive value a span can carry.

    Deliberately small. New types are added only when a detection layer
    actually produces them — not speculatively. Anything that does not fit
    one of the named categories is OTHER.
    """

    PERSON = "PERSON"
    ORG = "ORG"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    ADDRESS = "ADDRESS"
    ID_NUMBER = "ID_NUMBER"
    OTHER = "OTHER"


# Where a span came from. A string Literal rather than an enum because it names
# the *producer* (a detection layer), and these read most naturally as plain
# tags on the wire. "manual" is a span Sam created or edited by hand.
SpanSource = Literal["regex", "dictionary", "ner", "llm", "manual"]


class OutputMode(str, Enum):
    """How a confirmed span is rendered in the exported document.

    REDACT    — the value is removed/blacked out (e.g. "█████").
    ANONYMIZE — the value is replaced with a stable label (e.g. "[PERSON_1]").
    """

    REDACT = "REDACT"
    ANONYMIZE = "ANONYMIZE"


class Span(BaseModel):
    """A single addressed slice of the original text.

    Construct via `services.spans.make_span`, never directly, so the offset
    rule (text == original_text[start:end]) is always checked at creation.
    """

    id: str
    start: int = Field(ge=0, description="Codepoint index into original_text, inclusive.")
    end: int = Field(ge=0, description="Codepoint index into original_text, exclusive.")
    text: str = Field(description="The exact substring original_text[start:end].")
    type: PiiType
    confidence: float = Field(ge=0.0, le=1.0, description="0–1; how sure the source is.")
    source: SpanSource
    reason: str = Field(description="Human-readable 'why this span?' for explainability.")
    normalized_value: str | None = Field(
        default=None,
        description=(
            "Canonical form of the value (digits-only for phones, lowercased for "
            "emails), recorded so a later merge step can link duplicate "
            "occurrences. None when normalization does not apply."
        ),
    )


class SessionState(BaseModel):
    """Everything the server holds for one review session.

    `original_text` is immutable for the life of the session; all spans are
    expressed as offsets into it.
    """

    session_id: str
    original_text: str
    spans: list[Span] = Field(default_factory=list)
    output_mode: OutputMode = OutputMode.REDACT
