"""Test gate for detection layer 4 (LLM arbitration), run fully offline.

The model is the seam (`MODEL=cloud` | `gemma-local`); these tests inject a
deterministic stub `LlmClient` instead, so the layer's real work — windowing,
JSON validation, re-anchoring, the trigger gate, de-duplication — is exercised
without a network call. The oracle is the fixture's `name-with-no-anchor`
adversarial case: "Daniel Okafor", the supervisor introduced only relationally,
which regex and dictionary provably cannot catch.
"""
from __future__ import annotations

import json

import config
from services.detection import llm_layer

_SAMPLE = (config.FIXTURES_DIR / "sample-document.txt").read_text(encoding="utf-8")
_LABELS = json.loads((config.FIXTURES_DIR / "labels.json").read_text(encoding="utf-8"))


def _label(span_id: str) -> dict:
    return next(s for s in _LABELS["spans"] if s["id"] == span_id)


class _MockLlm:
    """Returns a fixed entity list as JSON on every call; counts invocations.

    Re-anchoring does the filtering: the entity only anchors in the window that
    actually contains it, so a dumb always-return stub still produces a correct,
    de-duplicated result.
    """

    def __init__(self, entities: list[dict]) -> None:
        self._entities = entities
        self.calls = 0

    def complete(self, *, system: str, user: str) -> str:
        self.calls += 1
        return json.dumps({"entities": self._entities})


def test_recovers_relational_name_offline() -> None:
    p3 = _label("p3")  # "Daniel Okafor" — the supervisor with no anchor
    mock = _MockLlm(
        [{"text": "Daniel Okafor", "type": "PERSON", "reason": "introduced as her supervisor"}]
    )

    spans = llm_layer.detect(_SAMPLE, client=mock)

    assert mock.calls > 0, "the model must actually be consulted"
    got = {(s.start, s.end, s.type.value) for s in spans}
    assert (p3["start"], p3["end"], "PERSON") in got

    span = next(s for s in spans if s.start == p3["start"])
    assert span.text == "Daniel Okafor" == _SAMPLE[span.start : span.end]  # offset rule
    assert span.source == "llm"
    assert span.confidence < 0.95, "no structural backup -> low confidence"
    assert span.reason

    # Despite overlapping windows, the name is emitted exactly once.
    assert sum(1 for s in spans if s.text == "Daniel Okafor") == 1


def test_drops_entities_not_present_in_text() -> None:
    # A name the document never contains finds no anchor and must be dropped —
    # this is the guard against the model hallucinating PII.
    mock = _MockLlm([{"text": "Imaginary Person", "type": "PERSON", "reason": "x"}])
    assert llm_layer.detect(_SAMPLE, client=mock) == []


def test_skips_spans_already_covered_by_earlier_layers() -> None:
    # The LLM earns its place only where earlier layers found nothing. If the
    # span is already covered, it is suppressed.
    p3 = _label("p3")
    mock = _MockLlm([{"text": "Daniel Okafor", "type": "PERSON", "reason": "x"}])

    spans = llm_layer.detect(_SAMPLE, covered_ranges=[(p3["start"], p3["end"])], client=mock)

    assert all(s.start != p3["start"] for s in spans)


def test_malformed_json_yields_no_spans() -> None:
    class _BadLlm:
        def complete(self, *, system: str, user: str) -> str:
            return "I'm sorry, I can't help with that."

    assert llm_layer.detect(_SAMPLE, client=_BadLlm()) == []


def test_trigger_gate_skips_passages_with_no_cue() -> None:
    # No trigger word -> no model call at all (cheap-first discipline).
    mock = _MockLlm([{"text": "Whoever", "type": "PERSON", "reason": "x"}])
    spans = llm_layer.detect("A plain sentence with nothing sensitive in it.", client=mock)
    assert spans == []
    assert mock.calls == 0


def test_resolve_disagreement_emits_span_when_model_says_pii() -> None:
    p3 = _label("p3")

    class _AgreeLlm:
        def complete(self, *, system: str, user: str) -> str:
            return json.dumps({"is_pii": True, "type": "PERSON", "reason": "a real individual"})

    span = llm_layer.resolve_disagreement(
        _SAMPLE, start=p3["start"], end=p3["end"], client=_AgreeLlm()
    )
    assert span is not None
    assert span.source == "llm"
    assert span.text == _SAMPLE[span.start : span.end]  # offset rule, same offsets


def test_resolve_disagreement_returns_none_when_model_says_safe() -> None:
    p3 = _label("p3")

    class _DenyLlm:
        def complete(self, *, system: str, user: str) -> str:
            return json.dumps({"is_pii": False, "type": "ORG", "reason": "public entity"})

    span = llm_layer.resolve_disagreement(
        _SAMPLE, start=p3["start"], end=p3["end"], client=_DenyLlm()
    )
    assert span is None
