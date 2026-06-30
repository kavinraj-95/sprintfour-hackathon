"""The output stage: turn an accepted span set into a shareable artifact.

Two genuinely different operations, selected by `OutputMode` (a user choice, not
config). Both consume the SAME accepted-span set; only this stage differs, so
flipping the mode re-renders without re-running detection.

REDACT — remove. The output is assembled ONLY from the text BETWEEN accepted
spans. Characters inside [start, end) are never copied into the output; a
constant marker stands in their place. This is structural removal, not a cover
over still-present data.

ANONYMIZE — replace. Each accepted span becomes a stable, type-aware token. The
SAME entity maps to the SAME token at every occurrence (so the document stays
readable and internally consistent); distinct entities of the same type get
distinct numbers. "Same entity" is decided by an identity key, which canonicalises
phone numbers so two formats of one number share a token (see _canonical_phone).

Pure: (text, accepted spans, mode) in -> (output_text, legend) out. No HTTP, no
session, no I/O — the route is a thin wrapper over render().
"""
from __future__ import annotations

import re
from collections.abc import Sequence

from errors import AppError
from models.api import LegendEntry
from models.contract import OutputMode, PiiType, Span

# A constant stand-in. It is NOT derived from the original characters, so no part
# of the redacted value reaches the output.
REDACT_MARKER = "[REDACTED]"

_NON_DIGITS = re.compile(r"\D")


def _canonical_phone(value: str) -> str:
    """Reduce a phone value to its national subscriber number for identity.

    '0412 887 905' and '+61 412 887 905' are the same number in two formats;
    digits-only ('0412887905' vs '61412887905') would NOT match. We strip a
    national trunk '0' or a leading '61' (AU) so both collapse to '412887905'.
    Deliberately AU-centric for this prototype; production would use a phone
    library (e.g. libphonenumber). Documented as a known simplification.
    """
    digits = _NON_DIGITS.sub("", value)
    if digits.startswith("0"):
        return digits[1:]
    if digits.startswith("61"):
        return digits[2:]
    return digits


def _identity_key(span: Span) -> tuple[str, str]:
    """A hashable identity for an entity, so its occurrences share one token.

    Type is part of the key so different types never collide. Phones use the
    canonical number; anything else with a normalized_value uses it (emails are
    lowercased upstream); otherwise we fall back to the casefolded text.
    """
    if span.type == PiiType.PHONE and span.normalized_value:
        return ("PHONE", _canonical_phone(span.normalized_value))
    if span.normalized_value:
        return (span.type.value, span.normalized_value)
    return (span.type.value, span.text.casefold())


def _ordered_disjoint(accepted: Sequence[Span]) -> list[Span]:
    """Sort accepted spans by start and reject overlaps.

    A reviewed, accepted set should be disjoint; overlapping ranges make the
    output ambiguous (which token wins?), so we surface a typed error rather
    than silently drop or mangle.
    """
    spans = sorted(accepted, key=lambda s: (s.start, s.end))
    for prev, cur in zip(spans, spans[1:]):
        if cur.start < prev.end:
            raise AppError(
                status_code=400,
                error="overlapping_accepted_spans",
                detail=(
                    f"Accepted spans overlap: [{prev.start},{prev.end}) and "
                    f"[{cur.start},{cur.end}). The accepted set must be disjoint."
                ),
            )
    return spans


def render(
    original_text: str,
    accepted: Sequence[Span],
    mode: OutputMode,
) -> tuple[str, list[LegendEntry]]:
    """Render the output text + legend for the chosen mode. Pure."""
    spans = _ordered_disjoint(accepted)

    # Assign a stable token per distinct entity, ordered by first occurrence.
    # For REDACT every token is the same marker; the per-entity grouping still
    # drives an accurate legend (how many distinct entities of each type went).
    token_by_identity: dict[tuple[str, str], str] = {}
    type_counters: dict[PiiType, int] = {}

    def token_for(span: Span) -> str:
        key = _identity_key(span)
        token = token_by_identity.get(key)
        if token is None:
            if mode is OutputMode.REDACT:
                token = REDACT_MARKER
            else:
                type_counters[span.type] = type_counters.get(span.type, 0) + 1
                token = f"[{span.type.value}_{type_counters[span.type]}]"
            token_by_identity[key] = token
        return token

    # Build output from the gaps; never copy original_text[start:end].
    out: list[str] = []
    cursor = 0
    legend_rows: dict[tuple[str, str], LegendEntry] = {}
    for span in spans:
        out.append(original_text[cursor : span.start])  # the gap before this span
        token = token_for(span)
        out.append(token)  # the replacement — original characters are dropped
        cursor = span.end

        identity = _identity_key(span)
        row = legend_rows.get(identity)
        if row is None:
            legend_rows[identity] = LegendEntry(
                token=token, type=span.type, occurrences=1
            )
        else:
            row.occurrences += 1
    out.append(original_text[cursor:])  # trailing gap

    return "".join(out), list(legend_rows.values())
