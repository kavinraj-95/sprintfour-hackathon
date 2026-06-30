// One row of the risk-ranked queue. Everything Sam needs to decide in one
// glance: sentence context with the span highlighted, a one-line reason, the
// type, a confidence cue, the linked "fixes N places" badge, and one-key
// actions. The card is the primary surface — the document is secondary.

import {
  TYPE_LABEL,
  TIERS,
  confidenceWord,
  placesCount,
  typeChipClass,
} from "../lib/review";
import type { ReviewItem } from "../types/contract";

// Highlight the span within its sentence. The backend gives us `sentence` and
// the absolute span text; we locate the span inside the sentence by string
// match (sentence is short, the value is distinctive) and bold-mark it.
function SentenceContext({ item }: { item: ReviewItem }) {
  const idx = item.sentence.indexOf(item.text);
  if (idx < 0) {
    // Fallback: show the value explicitly so it's never lost.
    return (
      <p className="text-sm leading-relaxed text-slate-600">
        …{" "}
        <mark className="rounded bg-yellow-200 px-0.5 font-medium text-slate-900">
          {item.text}
        </mark>{" "}
        …
      </p>
    );
  }
  const before = item.sentence.slice(0, idx);
  const after = item.sentence.slice(idx + item.text.length);
  return (
    <p className="text-sm leading-relaxed text-slate-600">
      {before}
      <mark className="rounded bg-yellow-200 px-0.5 font-medium text-slate-900">
        {item.text}
      </mark>
      {after}
    </p>
  );
}

function StatusBadge({ status }: { status: ReviewItem["status"] }) {
  if (status === "accepted")
    return (
      <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-700">
        ACCEPTED — will hide
      </span>
    );
  if (status === "dismissed")
    return (
      <span className="rounded bg-slate-200 px-1.5 py-0.5 text-[11px] font-semibold text-slate-600">
        DISMISSED — left visible
      </span>
    );
  return (
    <span className="rounded bg-white px-1.5 py-0.5 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-300">
      PENDING
    </span>
  );
}

export function QueueItemCard({
  item,
  index,
  active,
  onAccept,
  onFlip,
  onFocus,
}: {
  item: ReviewItem;
  index: number; // 1-based queue position, for the number-key hint
  active: boolean;
  onAccept: () => void;
  onFlip: () => void;
  onFocus: () => void;
}) {
  const tier = TIERS[item.tier];
  const places = placesCount(item);

  return (
    <article
      onClick={onFocus}
      className={`cursor-pointer border-l-4 ${tier.accent} rounded-r-lg bg-white p-3 shadow-sm ring-1 transition ${
        active ? "ring-2 ring-slate-900" : "ring-slate-200 hover:ring-slate-300"
      }`}
    >
      <div className="mb-1.5 flex items-center gap-2">
        <span className="font-mono text-[11px] text-slate-400">#{index}</span>
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${typeChipClass(item.type)}`}>
          {TYPE_LABEL[item.type]}
        </span>
        {item.linked_count > 0 && (
          <span className="rounded bg-red-600 px-1.5 py-0.5 text-[11px] font-bold text-white">
            fixes {places} places
          </span>
        )}
        <span className="ml-auto text-[11px] text-slate-400">
          {confidenceWord(item.confidence)} · {(item.confidence * 100) | 0}%
        </span>
      </div>

      <SentenceContext item={item} />

      <p className="mt-1.5 text-[12px] text-slate-500">
        <span className="font-medium text-slate-600">Why flagged:</span>{" "}
        {item.reason}
        {item.linked_count > 0 && (
          <span className="text-red-600">
            {" "}
            · same value appears {item.linked_count} other time
            {item.linked_count > 1 ? "s" : ""}
          </span>
        )}
      </p>

      <div className="mt-2 flex items-center gap-2">
        <StatusBadge status={item.status} />
        <div className="ml-auto flex gap-1.5">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAccept();
            }}
            className="rounded bg-slate-900 px-2.5 py-1 text-xs font-medium text-white hover:bg-slate-700"
          >
            {item.status === "accepted" ? "Re-hide" : "Accept"} (a)
            {item.linked_count > 0 ? ` · all ${places}` : ""}
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onFlip();
            }}
            className="rounded border border-slate-300 px-2.5 py-1 text-xs font-medium text-slate-700 hover:bg-slate-50"
          >
            {item.status === "dismissed" ? "Re-flag" : "Dismiss"} (x)
          </button>
        </div>
      </div>
    </article>
  );
}
