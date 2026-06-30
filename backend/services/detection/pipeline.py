"""Run the detection layers and merge them into one ranked list.

This is the orchestration seam the review API sits on. It runs each layer
defensively and reports, honestly, what happened to each — so the UI can say
"4 layers ran, NER skipped (model missing)" and never falsely declare a
document "clean". A layer that raises does NOT abort the pipeline; it is recorded
as degraded and the rest continue.

The LLM layer is OFF by default (`run_llm=False`): it is the only layer needing
network/a key, and the cheap layers already cover the structured + statistical
cases. Off is reported as a deliberate "skipped", not a silent omission.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from models.contract import Span
from services.detection import dictionary_layer, ner_layer, regex_layer
from services.detection.dictionary_layer import AllowlistRange, KnownEntity
from services.detection.merge import MergedSpan, merge


@dataclass(frozen=True)
class LayerStatus:
    name: str
    status: str   # "ok" | "skipped" | "error"
    count: int    # candidates contributed (0 when skipped/errored)
    detail: str   # human-readable note for the UI's "what ran" panel


@dataclass(frozen=True)
class PipelineResult:
    spans: list[MergedSpan]
    layers: list[LayerStatus]


def run(
    original_text: str,
    *,
    known_entities: Sequence[KnownEntity] = (),
    run_llm: bool = False,
) -> PipelineResult:
    """Run regex -> dictionary -> ner -> (llm) -> merge. Never raises per-layer."""
    candidates: list[Span] = []
    allowlist: list[AllowlistRange] = []
    layers: list[LayerStatus] = []

    # 1. regex (always available, deterministic)
    try:
        found = regex_layer.detect(original_text)
        candidates += found
        layers.append(LayerStatus("regex", "ok", len(found), "structured PII (phone/email/ID)"))
    except Exception as e:  # pragma: no cover - defensive
        layers.append(LayerStatus("regex", "error", 0, f"{type(e).__name__}: {e}"))

    # 2. dictionary + allowlist
    try:
        result = dictionary_layer.detect(original_text, known_entities=known_entities)
        candidates += result.spans
        allowlist = list(result.allowlist)
        layers.append(LayerStatus(
            "dictionary", "ok", len(result.spans),
            f"closed-world entities; {len(allowlist)} allowlisted range(s)",
        ))
    except Exception as e:  # pragma: no cover - defensive
        layers.append(LayerStatus("dictionary", "error", 0, f"{type(e).__name__}: {e}"))

    # 3. NER (may be unavailable if the spaCy model isn't installed)
    try:
        found = ner_layer.detect(original_text, allowlist=allowlist)
        candidates += found
        layers.append(LayerStatus("ner", "ok", len(found), "names / addresses (Presidio)"))
    except Exception as e:
        layers.append(LayerStatus(
            "ner", "error", 0,
            f"unavailable ({type(e).__name__}); install en_core_web_sm to enable",
        ))

    # 4. LLM arbitration (opt-in; relational/implicit PII)
    if run_llm:
        try:
            covered = [(c.start, c.end) for c in candidates]
            found = llm_detect(original_text, covered)
            candidates += found
            layers.append(LayerStatus("llm", "ok", len(found), "relational/implicit PII"))
        except Exception as e:
            layers.append(LayerStatus("llm", "error", 0, f"unavailable ({type(e).__name__})"))
    else:
        layers.append(LayerStatus("llm", "skipped", 0, "disabled (offline/no key) — enable to catch relational PII"))

    return PipelineResult(spans=merge(candidates, allowlist=allowlist), layers=layers)


def llm_detect(original_text: str, covered: list[tuple[int, int]]) -> list[Span]:
    """Thin indirection so `run` need not import the LLM layer unless enabled."""
    from services.detection import llm_layer

    return llm_layer.detect(original_text, covered_ranges=covered)
