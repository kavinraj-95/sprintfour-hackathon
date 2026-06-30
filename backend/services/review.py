"""The correction-session service: state, reversible actions, and rendering.

Holds one review per session: the merged candidate queue, the reviewer's
decision on each item, the layers-ran report, and a flat action log so every
gesture is undoable (a slip never silently destroys a correction). Pure-ish:
all mutation goes through `apply_action`, all reads through `state`.

Decisions: every candidate starts `pending`. `accept` confirms it (it WILL be
acted on at export); `dismiss` flips it to a false positive (left in place);
`add_missed` injects a manual span the detectors left visible (accepted). Export
is gated while any high-risk (tier-1) item is still `pending`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from errors import AppError
from models.api import (
    ExportResult,
    LayerStatus,
    LegendEntry,
    OccurrenceRef,
    ReviewCounts,
    ReviewItem,
    ReviewState,
)
from models.contract import OutputMode, PiiType, Span
from services import redaction
from services.detection import pipeline
from services.detection.dictionary_layer import KnownEntity
from services.detection.merge import MergedSpan, RiskTier
from services.spans import make_span

_SENTENCE_BOUNDARY = re.compile(r"[.!?\n]")


def _sentence(text: str, start: int, end: int) -> str:
    """The sentence containing [start,end), trimmed — one-glance queue context."""
    left = max((m.end() for m in _SENTENCE_BOUNDARY.finditer(text, 0, start)), default=0)
    nxt = _SENTENCE_BOUNDARY.search(text, end)
    right = nxt.start() if nxt else len(text)
    return text[left:right].strip()


@dataclass
class _Action:
    """One reversible step — possibly spanning several linked occurrences.

    A decision on a linked item resolves the whole group atomically, so the
    action records every (id, previous_decision) it changed and a single undo
    reverts all of them. `added_id` is set only for add_missed.
    """

    kind: str                                  # "decision" | "add_missed"
    changes: list[tuple[str, str | None]] = field(default_factory=list)
    added_id: str | None = None


@dataclass
class ReviewSession:
    session_id: str
    original_text: str
    output_mode: OutputMode
    layers: list[LayerStatus]
    items: dict[str, MergedSpan] = field(default_factory=dict)
    decisions: dict[str, str] = field(default_factory=dict)
    log: list[_Action] = field(default_factory=list)


class ReviewStore:
    def __init__(self) -> None:
        self._sessions: dict[str, ReviewSession] = {}

    def put(self, s: ReviewSession) -> None:
        self._sessions[s.session_id] = s

    def get(self, session_id: str) -> ReviewSession:
        s = self._sessions.get(session_id)
        if s is None:
            raise AppError(404, "session_not_found", f"No review session {session_id!r}.")
        return s


store = ReviewStore()


def create(
    *,
    session_id: str,
    text: str,
    output_mode: OutputMode,
    known_entities: tuple[KnownEntity, ...] = (),
    run_llm: bool = False,
) -> ReviewSession:
    """Run the pipeline, seed the queue (all pending), and store the session."""
    result = pipeline.run(text, known_entities=known_entities, run_llm=run_llm)
    layers = [LayerStatus(name=l.name, status=l.status, count=l.count, detail=l.detail)
              for l in result.layers]
    session = ReviewSession(
        session_id=session_id,
        original_text=text,
        output_mode=output_mode,
        layers=layers,
        items={m.id: m for m in result.spans},
        decisions={m.id: "pending" for m in result.spans},
    )
    store.put(session)
    return session


# ----------------------------------------------------------------- actions ----
def apply_action(
    session: ReviewSession,
    *,
    type: str,
    target_id: str | None = None,
    start: int | None = None,
    end: int | None = None,
    pii_type: PiiType | None = None,
) -> None:
    if type in ("accept", "dismiss"):
        _set_decision(session, target_id, "accepted" if type == "accept" else "dismissed")
    elif type == "add_missed":
        _add_missed(session, start, end, pii_type)
    elif type == "undo":
        _undo(session)
    else:
        raise AppError(400, "unknown_action", f"Unknown action type {type!r}.")


def _linked_group(session: ReviewSession, target_id: str) -> list[str]:
    """The target plus every queue item addressing a linked occurrence of it.

    Matching is by offset (the merge step records linked occurrences as ranges),
    so one gesture on a duplicated value resolves all of its occurrences.
    """
    target = session.items[target_id]
    linked_ranges = {(o.start, o.end) for o in target.linked}
    group = [target_id]
    group += [
        m.id for m in session.items.values()
        if m.id != target_id and (m.start, m.end) in linked_ranges
    ]
    return group


def _set_decision(session: ReviewSession, target_id: str | None, decision: str) -> None:
    if target_id is None or target_id not in session.items:
        raise AppError(400, "unknown_item", f"No queue item {target_id!r}.")
    group = _linked_group(session, target_id)
    changes = [(gid, session.decisions[gid]) for gid in group]
    session.log.append(_Action("decision", changes=changes))
    for gid in group:
        session.decisions[gid] = decision


def _add_missed(session, start, end, pii_type) -> None:
    if start is None or end is None:
        raise AppError(400, "missing_selection", "add_missed needs start and end.")
    # make_span enforces the offset rule; a bad selection -> typed error, not a
    # silently wrong redaction.
    span = make_span(
        id=f"manual:{start}-{end}",
        original_text=session.original_text,
        start=start, end=end,
        type=pii_type or PiiType.OTHER,
        confidence=1.0, source="manual",
        reason="Marked as missed PII by the reviewer.",
    )
    item = MergedSpan(
        id=span.id, start=span.start, end=span.end, text=span.text, type=span.type,
        confidence=1.0, sources=["manual"], reason=span.reason,
        normalized_value=None, tier=RiskTier.HIGH, linked=[],
    )
    session.items[item.id] = item
    session.decisions[item.id] = "accepted"
    session.log.append(_Action("add_missed", added_id=item.id))


def _undo(session: ReviewSession) -> None:
    if not session.log:
        raise AppError(400, "nothing_to_undo", "The action log is empty.")
    action = session.log.pop()
    if action.kind == "decision":
        for gid, prev in action.changes:
            if prev is not None:
                session.decisions[gid] = prev
    elif action.kind == "add_missed" and action.added_id is not None:
        session.items.pop(action.added_id, None)
        session.decisions.pop(action.added_id, None)


# ------------------------------------------------------------------- reads ----
def _to_item(session: ReviewSession, m: MergedSpan) -> ReviewItem:
    return ReviewItem(
        id=m.id, start=m.start, end=m.end, text=m.text, type=m.type,
        confidence=m.confidence, sources=list(m.sources), reason=m.reason,
        normalized_value=m.normalized_value, tier=int(m.tier),
        linked=[OccurrenceRef(start=o.start, end=o.end) for o in m.linked],
        linked_count=len(m.linked),
        status=session.decisions[m.id],
        sentence=_sentence(session.original_text, m.start, m.end),
    )


def _ordered_items(session: ReviewSession) -> list[ReviewItem]:
    items = [_to_item(session, m) for m in session.items.values()]
    items.sort(key=lambda it: (it.tier, it.start))
    return items


def state(session: ReviewSession) -> ReviewState:
    queue = _ordered_items(session)
    decisions = session.decisions
    counts = ReviewCounts(
        tier1=sum(1 for it in queue if it.tier == 1),
        tier2=sum(1 for it in queue if it.tier == 2),
        tier3=sum(1 for it in queue if it.tier == 3),
        accepted=sum(1 for v in decisions.values() if v == "accepted"),
        dismissed=sum(1 for v in decisions.values() if v == "dismissed"),
        pending=sum(1 for v in decisions.values() if v == "pending"),
        unresolved_high_risk=sum(1 for it in queue if it.tier == 1 and it.status == "pending"),
    )
    return ReviewState(
        session_id=session.session_id, original_text=session.original_text,
        output_mode=session.output_mode, layers=session.layers, queue=queue, counts=counts,
    )


def _accepted_spans(session: ReviewSession) -> list[Span]:
    out: list[Span] = []
    for m in session.items.values():
        if session.decisions[m.id] != "accepted":
            continue
        out.append(make_span(
            id=m.id, original_text=session.original_text, start=m.start, end=m.end,
            type=m.type, confidence=m.confidence, source=m.sources[0] if m.sources else "manual",
            reason=m.reason, normalized_value=m.normalized_value,
        ))
    return out


def render_preview(session: ReviewSession, mode: OutputMode) -> tuple[str, list[LegendEntry]]:
    """Live preview from the currently-accepted set. Persists the chosen mode."""
    session.output_mode = mode
    return redaction.render(session.original_text, _accepted_spans(session), mode)


def export(session: ReviewSession, mode: OutputMode, *, confirm: bool) -> ExportResult:
    """Render the artifact, or gate it while high-risk items are unresolved.

    The gate is authoritative: with unresolved tier-1 items and no `confirm`, no
    output is produced — only the list of what still needs review is returned.
    """
    session.output_mode = mode
    queue = _ordered_items(session)
    unresolved = [it for it in queue if it.tier == 1 and it.status == "pending"]
    if unresolved and not confirm:
        return ExportResult(gated=True, unresolved=unresolved)
    output_text, legend = redaction.render(session.original_text, _accepted_spans(session), mode)
    return ExportResult(gated=False, output_text=output_text, legend=legend)
