// SECONDARY surface: the document, for orientation only. It renders
// original_text with:
//   - accepted spans shown as their redaction / anonymization marker,
//   - pending flagged spans highlighted (confidence encoded as opacity),
//   - dismissed spans left as plain visible text (Sam chose to keep them).
// And it is where mark-missed lives: select any text the tool missed and the
// selection -> codepoint [start,end) -> add_missed. One gesture, reversible.
//
// Slicing is codepoint-safe (the offset rule): we index a precomputed
// Array.from(original_text) so astral characters never shift the highlight.

import { useMemo, useRef } from "react";
import {
  TYPE_LABEL,
  codepoints,
  confidenceOpacity,
  sliceCp,
} from "../lib/review";
import type { OutputMode, PiiType, ReviewItem } from "../types/contract";

// Map a DOM selection back to codepoint offsets in original_text. The rendered
// text is broken into segments, each carrying its codepoint start; we walk up
// to the segment node and add the in-segment UTF-16 offset converted to
// codepoints. Kept defensive: returns null if the selection escapes the doc.
interface Segment {
  cpStart: number;
  cpEnd: number;
  text: string;
  item: ReviewItem | null;
}

function buildSegments(
  cps: string[],
  items: ReviewItem[],
): Segment[] {
  // Only spans that visibly affect rendering: accepted (marker) or pending
  // (highlight). Dismissed render as plain text, so they're not segment-split.
  const active = items
    .filter((it) => it.status === "accepted" || it.status === "pending")
    .slice()
    .sort((a, b) => a.start - b.start);

  const segs: Segment[] = [];
  let cursor = 0;
  for (const it of active) {
    if (it.start < cursor) continue; // skip overlaps defensively
    if (it.start > cursor) {
      segs.push({
        cpStart: cursor,
        cpEnd: it.start,
        text: sliceCp(cps, cursor, it.start),
        item: null,
      });
    }
    segs.push({
      cpStart: it.start,
      cpEnd: it.end,
      text: sliceCp(cps, it.start, it.end),
      item: it,
    });
    cursor = it.end;
  }
  if (cursor < cps.length) {
    segs.push({
      cpStart: cursor,
      cpEnd: cps.length,
      text: sliceCp(cps, cursor, cps.length),
      item: null,
    });
  }
  return segs;
}

function marker(item: ReviewItem, mode: OutputMode): string {
  if (mode === "REDACT") return "█".repeat(Math.max(3, item.text.length));
  return `[${item.type}]`;
}

export function DocumentView({
  originalText,
  items,
  mode,
  onMarkMissed,
}: {
  originalText: string;
  items: ReviewItem[];
  mode: OutputMode;
  onMarkMissed: (start: number, end: number, type: PiiType) => void;
}) {
  const cps = useMemo(() => codepoints(originalText), [originalText]);
  const segments = useMemo(() => buildSegments(cps, items), [cps, items]);
  const rootRef = useRef<HTMLDivElement>(null);

  // Resolve the current selection to codepoint offsets using data attributes
  // on the segment spans. Each segment span carries its codepoint start.
  function captureSelection(): { start: number; end: number } | null {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed || !rootRef.current) return null;
    const range = sel.getRangeAt(0);
    const startSeg = segOffset(range.startContainer, range.startOffset);
    const endSeg = segOffset(range.endContainer, range.endOffset);
    if (startSeg == null || endSeg == null) return null;
    const start = Math.min(startSeg, endSeg);
    const end = Math.max(startSeg, endSeg);
    if (end <= start) return null;
    return { start, end };
  }

  // Convert a (node, utf16 offset) into an absolute codepoint offset.
  function segOffset(node: Node, utf16Offset: number): number | null {
    let el: HTMLElement | null =
      node.nodeType === Node.TEXT_NODE
        ? (node.parentElement as HTMLElement)
        : (node as HTMLElement);
    while (el && el.dataset.cpstart === undefined) {
      el = el.parentElement;
    }
    if (!el || el.dataset.cpstart === undefined) return null;
    const base = Number(el.dataset.cpstart);
    // Convert the in-text UTF-16 offset to codepoints within this segment.
    const segText = el.textContent ?? "";
    const cpInSeg = Array.from(segText.slice(0, utf16Offset)).length;
    return base + cpInSeg;
  }

  function handleMarkMissed() {
    const span = captureSelection();
    if (!span) return;
    const selected = sliceCp(cps, span.start, span.end).trim();
    if (!selected) return;
    onMarkMissed(span.start, span.end, "OTHER");
    window.getSelection()?.removeAllRanges();
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
        <div>
          <h2 className="text-sm font-semibold text-slate-700">
            Document (orientation)
          </h2>
          <p className="text-[11px] text-slate-400">
            Select any missed text below, then press{" "}
            <kbd className="rounded bg-slate-100 px-1">m</kbd> or the button to
            flag it. Confidence shown as opacity.
          </p>
        </div>
        <button
          onClick={handleMarkMissed}
          className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
        >
          Flag selection as missed (m)
        </button>
      </header>

      <div
        ref={rootRef}
        className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap px-4 py-3 font-mono text-[13px] leading-relaxed text-slate-800 selection:bg-yellow-200"
      >
        {segments.map((seg) => {
          if (!seg.item) {
            return (
              <span key={seg.cpStart} data-cpstart={seg.cpStart}>
                {seg.text}
              </span>
            );
          }
          const it = seg.item;
          if (it.status === "accepted") {
            return (
              <span
                key={seg.cpStart}
                data-cpstart={seg.cpStart}
                title={`${TYPE_LABEL[it.type]} — accepted`}
                className="rounded bg-slate-900 px-0.5 font-semibold text-slate-900"
              >
                {marker(it, mode)}
              </span>
            );
          }
          // pending — highlight, opacity by confidence
          return (
            <span
              key={seg.cpStart}
              data-cpstart={seg.cpStart}
              title={`${TYPE_LABEL[it.type]} — pending (${(it.confidence * 100) | 0}%)`}
              className="rounded bg-yellow-200 px-0.5 ring-1 ring-yellow-400"
              style={{ opacity: confidenceOpacity(it.confidence) }}
            >
              {seg.text}
            </span>
          );
        })}
      </div>
    </section>
  );
}
