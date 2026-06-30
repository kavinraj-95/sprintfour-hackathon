"""Layer 4 of the detection pipeline: the LLM as ARBITRATOR, not detector.

Per `layer-discipline`, the model is the most expensive, least certain tool, so
it runs last and only on the genuinely ambiguous remainder — never blindly over
the whole document. This layer exists for the two cases the structure-blind
layers (regex, dictionary, NER) provably cannot reach:

  1. RELATIONAL / IMPLICIT PII. A name introduced only by its relationship to
     someone — "her supervisor, Daniel Okafor", "the doctor who treated her,
     Dr. Patel". Regex has no shape to match, the dictionary has no prior entry,
     and NER often misses a bare name with no title. The seeded fixture's
     `name-with-no-anchor` adversarial case is exactly this. We invoke the model
     only on passages where earlier layers found nothing yet a trigger word
     (a role, a medical or financial cue) signals a person may be hiding.

  2. DISAGREEMENT. The dictionary allowlisted a span as safe but NER calls it a
     PERSON. `resolve_disagreement` shows the model the surrounding sentence and
     asks which layer is right.

Because the LLM has no structural backup, every span it emits carries
`source="llm"` and a deliberately LOW default confidence — the merge step (built
later) will rank these into the soft-review tier, never auto-redact them.

Three properties make the model's output safe to trust:

  * SLIDING WINDOW with overlap STRICTLY LARGER than the longest entity we expect
    (`_OVERLAP_CHARS > _MAX_ENTITY_CHARS`), so no entity can be split across a
    chunk boundary and missed in both halves. Overlapping hits are de-duplicated
    by offset.
  * VALIDATION. The model's reply is parsed as JSON; anything malformed or
    structurally wrong is discarded, not trusted.
  * RE-ANCHORING. A returned value is located in the real text and its offsets
    are asserted to slice back to exactly that value (`make_span` enforces the
    offset rule). A name the model invented but the document never contained
    finds no anchor and is dropped — that is the guard against hallucination.

This layer does NOT merge its spans with the other layers' — that is the merge
step, built later. It only produces a clean, re-anchored list of `llm` spans.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterator, Sequence

import config
from models.contract import PiiType, Span
from services.spans import make_span

from .llm_client import LlmClient, get_llm_client

# No structural backup means low confidence: flagged for review, never trusted
# enough to redact on its own. The merge step keys its risk tier off `source`.
_LLM_CONFIDENCE = 0.55

# Sliding-window geometry. The invariant that matters: the overlap must be
# strictly larger than the longest entity we could expect, so any single entity
# falls wholly inside at least one window and is never truncated at a boundary.
_MAX_ENTITY_CHARS = 80
_WINDOW_CHARS = 800
_OVERLAP_CHARS = 120
assert _OVERLAP_CHARS > _MAX_ENTITY_CHARS, "overlap must exceed the longest entity"
assert _WINDOW_CHARS > _OVERLAP_CHARS, "window must be larger than its overlap"

# Cheap gate for case 1: a passage is only worth a model call if it carries a
# cue that a person might be present — a relationship/role word, a medical
# context word, or a financial one. Earlier layers run first; the model is spent
# only on what they left behind near one of these words. Word-boundaried and
# case-insensitive so "Dr" matches "Dr." but not "Drive".
_TRIGGER_WORDS: tuple[str, ...] = (
    # relational / role
    "supervisor", "manager", "colleague", "partner", "spouse", "wife",
    "husband", "mother", "father", "son", "daughter", "brother", "sister",
    "friend", "neighbour", "neighbor", "landlord", "tenant", "employer",
    "employee", "assistant", "secretary", "director", "officer", "contact",
    "referred", "introduced", "he", "she", "his", "her", "him",
    # medical
    "doctor", "dr", "physician", "nurse", "patient", "diagnosed", "diagnosis",
    "prescribed", "treatment", "clinic", "hospital", "condition", "symptoms",
    # financial
    "account", "salary", "payment", "invoice", "bank", "loan", "mortgage",
    "policy", "claim", "premium",
)
_TRIGGER_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(w) for w in _TRIGGER_WORDS) + r")\b",
    re.IGNORECASE,
)

_TYPE_MAP = {t.value: t for t in PiiType}

_SYSTEM_PROMPT = (
    "You find personally identifying information (PII) that other, simpler "
    "detectors miss: a person's name introduced only by their relationship or "
    "role (\"her supervisor, NAME\"; \"the doctor who saw her, Dr NAME\"), or a "
    "person/organisation tied to a medical or financial detail. Only report a "
    "span that is genuinely sensitive PII. Copy the value EXACTLY as it appears "
    "in the text — do not paraphrase, expand, or correct it. If there is no such "
    "PII, return an empty list. Respond with ONLY a JSON object of the form "
    '{"entities": [{"text": <exact substring>, "type": <PERSON|ORG|EMAIL|PHONE|'
    'ADDRESS|ID_NUMBER|OTHER>, "reason": <short why>}]} and nothing else.'
)


def _user_prompt(chunk: str) -> str:
    return f"Find relational or implicit PII in this passage:\n\n{chunk}"


def _windows(text: str) -> Iterator[tuple[int, str]]:
    """Yield (absolute_start, chunk) covering `text` with overlapping windows.

    The step leaves `_OVERLAP_CHARS` of shared text between consecutive windows;
    since that overlap exceeds the longest entity, every entity sits wholly in
    at least one window. The de-dupe in `detect` removes the resulting repeats.
    """
    n = len(text)
    if n == 0:
        return
    step = _WINDOW_CHARS - _OVERLAP_CHARS
    start = 0
    while start < n:
        yield start, text[start : start + _WINDOW_CHARS]
        if start + _WINDOW_CHARS >= n:
            break
        start += step


def _parse_entities(raw: str) -> list[dict]:
    """Parse the model's reply into a list of entity dicts; never raise.

    Validation, not trust: a non-JSON reply, a wrong shape, or a non-list
    `entities` all collapse to an empty list. The caller treats "couldn't parse"
    and "found nothing" identically — the model gets no benefit of the doubt.
    """
    text = raw.strip()
    if text.startswith("```"):
        # Strip a ```json ... ``` fence if the model wrapped its answer.
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return []

    if isinstance(parsed, dict):
        parsed = parsed.get("entities", [])
    if not isinstance(parsed, list):
        return []
    return [e for e in parsed if isinstance(e, dict) and isinstance(e.get("text"), str)]


def _map_type(raw_type: object) -> PiiType:
    if isinstance(raw_type, str):
        return _TYPE_MAP.get(raw_type.strip().upper(), PiiType.OTHER)
    return PiiType.OTHER


def _overlaps(start: int, end: int, ranges: Sequence[tuple[int, int]]) -> bool:
    return any(start < b and a < end for a, b in ranges)


def _find_unused(chunk: str, value: str, used_local: set[int]) -> int:
    """First index of `value` in `chunk` not already claimed in this window.

    A value can legitimately appear more than once in a passage; this hands out
    a fresh occurrence each call so repeats anchor to distinct offsets instead
    of collapsing onto the first match.
    """
    idx = chunk.find(value)
    while idx != -1 and idx in used_local:
        idx = chunk.find(value, idx + 1)
    return idx


def detect(
    original_text: str,
    *,
    covered_ranges: Sequence[tuple[int, int]] = (),
    client: LlmClient | None = None,
    model: str | None = None,
) -> list[Span]:
    """Case 1: recover relational/implicit PII the earlier layers left behind.

    `covered_ranges` are the [start, end) spans earlier layers already claimed;
    the model is invoked only on windows carrying a trigger word, and any hit
    overlapping a covered range is dropped — the model adds value precisely
    where the others found nothing. Pure given a fixed `client`: a deterministic
    stub makes the whole layer testable offline.

    Returns re-anchored `source="llm"` spans, ordered by start, de-duplicated by
    offset. No merging with other layers happens here.
    """
    client = client or get_llm_client(model)

    found: dict[tuple[int, int], Span] = {}
    for w_start, chunk in _windows(original_text):
        if not _TRIGGER_RE.search(chunk):
            continue  # no cue a person is hiding here — not worth a model call

        entities = _parse_entities(client.complete(system=_SYSTEM_PROMPT, user=_user_prompt(chunk)))
        used_local: set[int] = set()
        for ent in entities:
            value = ent["text"]
            if not value:
                continue
            local_idx = _find_unused(chunk, value, used_local)
            if local_idx == -1:
                continue  # the model's value is not literally in the passage -> drop
            used_local.add(local_idx)

            start = w_start + local_idx
            end = start + len(value)
            key = (start, end)
            if key in found or _overlaps(start, end, covered_ranges):
                continue  # already seen via the overlap, or an earlier layer owns it

            # make_span asserts value == original_text[start:end]; a wrong offset
            # raises rather than silently redacting the wrong slice.
            found[key] = make_span(
                id=f"llm:{start}-{end}",
                original_text=original_text,
                start=start,
                end=end,
                text=value,
                type=_map_type(ent.get("type")),
                confidence=_LLM_CONFIDENCE,
                source="llm",
                reason=_reason(ent, "relational/implicit PII the earlier layers missed"),
            )

    return [found[k] for k in sorted(found)]


def resolve_disagreement(
    original_text: str,
    *,
    start: int,
    end: int,
    client: LlmClient | None = None,
    model: str | None = None,
) -> Span | None:
    """Case 2: the dictionary allowlisted [start, end) but NER called it PERSON.

    Shows the model the surrounding sentence and asks whether the span is real
    PII. Returns a re-anchored `source="llm"` span at the SAME offsets if the
    model agrees it is sensitive, else None. The offsets are fixed by the
    disagreeing layers; only the verdict comes from the model.
    """
    client = client or get_llm_client(model)
    value = original_text[start:end]
    sentence = _surrounding_sentence(original_text, start, end)

    system = (
        "You arbitrate a disagreement: one detector marked the quoted span as a "
        "safe, non-sensitive name; another flagged it as a person's name. Using "
        "the surrounding sentence, decide if it is genuinely sensitive PII (a "
        "specific individual whose identity should be protected) rather than a "
        "public entity or generic term. Respond with ONLY "
        '{"is_pii": <true|false>, "type": <PERSON|ORG|OTHER>, "reason": <short why>}.'
    )
    user = f'Span: "{value}"\nSentence: "{sentence}"'

    verdict = _parse_verdict(client.complete(system=system, user=user))
    if not verdict.get("is_pii"):
        return None

    return make_span(
        id=f"llm:{start}-{end}",
        original_text=original_text,
        start=start,
        end=end,
        text=value,
        type=_map_type(verdict.get("type")) or PiiType.PERSON,
        confidence=_LLM_CONFIDENCE,
        source="llm",
        reason=_reason(verdict, "dictionary/NER disagreement resolved by the model"),
    )


def _reason(payload: dict, fallback: str) -> str:
    given = payload.get("reason")
    return given.strip() if isinstance(given, str) and given.strip() else fallback


def _parse_verdict(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()
    try:
        parsed = json.loads(text)
    except (ValueError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _surrounding_sentence(text: str, start: int, end: int) -> str:
    """The sentence containing [start, end), bounded by sentence punctuation."""
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right_dot = text.find(".", end)
    right_nl = text.find("\n", end)
    candidates = [r for r in (right_dot, right_nl) if r != -1]
    right = min(candidates) + 1 if candidates else len(text)
    return text[left:right].strip()
