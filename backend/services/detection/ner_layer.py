"""Layer 3 of the detection pipeline: statistical NER (Presidio + spaCy).

Per `layer-discipline`, this layer reasons about the *contextual* PII that the
cheap, certain layers cannot: names and addresses that have no fixed surface
form and are not on any known list. It is the first layer whose answers are
probabilistic, so its confidences sit strictly below the regex/dictionary band.

Why Presidio (and not GLiNER): see fixtures/ner-benchmark.md. Both were on the
table; GLiNER was cut because it needs torch (~0.5 GB). Presidio gives full
PERSON recall (including the no-anchor 'Daniel Okafor'); its one gap — full
street addresses — is closed with a targeted Presidio pattern recognizer.

Responsibilities and boundaries:
- Emits only PERSON / ORG / ADDRESS. Presidio also recognises phones, emails,
  SSNs, etc.; those belong to the regex layer and are filtered out here so the
  layers stay disjoint.
- RESPECTS THE ALLOWLIST. The dictionary layer marks PII-shaped-but-safe ranges
  (e.g. a public org name). Statistical NER will happily flag those — Presidio
  even mislabels 'Coastline Mutual' as a PERSON — so any candidate overlapping
  an allowlist range is dropped before it becomes a span.

The model is loaded lazily and once: importing this module is cheap; the spaCy
model only loads on the first detect() call.
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from models.contract import PiiType, Span
from services.detection.dictionary_layer import AllowlistRange
from services.spans import make_span

# NER is contextual and statistical — never as sure as a regex or a known-list
# hit. Confidences are capped here so a downstream merge always ranks a
# structural (regex/dictionary, ~0.98+) agreement above a bare NER guess.
_NER_CONFIDENCE_CEILING = 0.85

# Presidio entity type -> (our PiiType, reason). Anything not in this map is not
# this layer's job and is dropped (phones/emails/SSNs are the regex layer's).
_ENTITY_MAP: dict[str, tuple[PiiType, str]] = {
    "PERSON": (PiiType.PERSON, "NER (Presidio/spaCy) classified this as a person name"),
    "ORGANIZATION": (PiiType.ORG, "NER (Presidio/spaCy) classified this as an organisation"),
    "ORG": (PiiType.ORG, "NER (Presidio/spaCy) classified this as an organisation"),
    "LOCATION": (PiiType.ADDRESS, "NER (Presidio/spaCy) classified this as a location"),
    "STREET_ADDRESS": (
        PiiType.ADDRESS,
        "Presidio street-address recognizer matched a full street address",
    ),
}

# Targeted street-address shape: a street number, a street-type keyword, and a
# trailing 4-digit postcode on the same line. High precision; closes the one
# gap Presidio's spaCy NER has (it does not emit full street addresses).
_ADDRESS_REGEX = (
    r"\b\d{1,5}\s+[A-Z][A-Za-z]+(?:\s+[A-Za-z]+)*?\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|"
    r"Boulevard|Blvd|Way|Terrace|Tce|Crescent|Cres)\b.*?\b\d{4}\b"
)

_analyzer = None  # lazily-built singleton (loading the spaCy model is the slow part)


def _get_analyzer():
    global _analyzer
    if _analyzer is None:
        # Imported here so merely importing this module does not pull Presidio.
        from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
        from presidio_analyzer.nlp_engine import NlpEngineProvider

        cfg = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
        }
        nlp_engine = NlpEngineProvider(nlp_configuration=cfg).create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"])
        analyzer.registry.add_recognizer(
            PatternRecognizer(
                supported_entity="STREET_ADDRESS",
                patterns=[Pattern(name="street_address", regex=_ADDRESS_REGEX, score=0.8)],
            )
        )
        _analyzer = analyzer
    return _analyzer


@dataclass(frozen=True)
class _Candidate:
    start: int
    end: int
    type: PiiType
    reason: str
    confidence: float


def _suppressed(start: int, end: int, allowlist: Sequence[AllowlistRange]) -> bool:
    """True if [start, end) overlaps any allowlisted (non-sensitive) range."""
    return any(start < a.end and a.start < end for a in allowlist)


def _resolve_overlaps(cands: list[_Candidate]) -> list[_Candidate]:
    """Drop a candidate that overlaps an already-kept one (longer/higher wins).

    Mostly matters when the LOCATION and STREET_ADDRESS recognizers both fire on
    the same address; we keep a single span rather than emit two.
    """
    ordered = sorted(cands, key=lambda c: (-(c.end - c.start), -c.confidence, c.start))
    kept: list[_Candidate] = []
    for c in ordered:
        if any(c.start < k.end and k.start < c.end for k in kept):
            continue
        kept.append(c)
    return sorted(kept, key=lambda c: c.start)


def detect(
    original_text: str,
    *,
    allowlist: Sequence[AllowlistRange] = (),
) -> list[Span]:
    """Detect contextual PII (PERSON / ORG / ADDRESS). Spans ordered by start.

    `allowlist` are ranges from the dictionary layer that must not be flagged.
    """
    results = _get_analyzer().analyze(text=original_text, language="en")

    cands: list[_Candidate] = []
    for r in results:
        mapped = _ENTITY_MAP.get(r.entity_type)
        if mapped is None:
            continue  # not a type this layer owns
        if _suppressed(r.start, r.end, allowlist):
            continue  # on the dictionary allowlist — leave it alone
        pii_type, reason = mapped
        cands.append(
            _Candidate(
                start=r.start,
                end=r.end,
                type=pii_type,
                reason=reason,
                confidence=round(min(r.score, _NER_CONFIDENCE_CEILING), 2),
            )
        )

    return [
        make_span(
            id=f"ner:{c.start}-{c.end}",
            original_text=original_text,
            start=c.start,
            end=c.end,
            type=c.type,
            confidence=c.confidence,
            source="ner",
            reason=c.reason,
        )
        for c in _resolve_overlaps(cands)
    ]
