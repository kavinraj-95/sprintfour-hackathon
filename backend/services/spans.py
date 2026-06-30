"""The one place spans are created — so the offset rule is enforced once.

Every detection layer, the missed-PII finder, and Sam's manual edits all build
spans through `make_span`. It is the single creation site that has both the
candidate's claimed text and the `original_text` in hand, which is the only
place the offset invariant can actually be checked. See models/contract.py.
"""
from __future__ import annotations

from errors import AppError
from models.contract import PiiType, Span, SpanSource


def make_span(
    *,
    id: str,
    original_text: str,
    start: int,
    end: int,
    type: PiiType,
    confidence: float,
    source: SpanSource,
    reason: str,
    text: str | None = None,
) -> Span:
    """Build a Span and assert it addresses exactly what it claims to.

    Enforces the offset rule: the resulting `text` equals
    `original_text[start:end]` (codepoint indices, end-exclusive).

    A detection layer typically *captured* a piece of text and then computed
    its offsets. Pass that captured value as `text` and we verify the offsets
    actually point at it — a mismatch means the layer's offsets are wrong, and
    a wrong offset silently redacts the wrong slice (or misses the real value).
    We catch that here and raise a typed error instead of letting it through.
    If `text` is omitted we take the slice as authoritative.
    """
    if not (0 <= start <= end <= len(original_text)):
        raise AppError(
            status_code=500,
            error="span_offsets_out_of_range",
            detail=(
                f"Span {id!r} has offsets [{start}, {end}) outside "
                f"text of length {len(original_text)}."
            ),
        )

    sliced = original_text[start:end]
    if text is not None and text != sliced:
        raise AppError(
            status_code=500,
            error="span_offset_mismatch",
            detail=(
                f"Span {id!r}: claimed text {text!r} does not match "
                f"original_text[{start}:{end}] == {sliced!r}."
            ),
        )

    span = Span(
        id=id,
        start=start,
        end=end,
        text=sliced,
        type=type,
        confidence=confidence,
        source=source,
        reason=reason,
    )

    # The offset rule, stated exactly as the contract states it.
    assert span.text == original_text[span.start : span.end]
    return span
