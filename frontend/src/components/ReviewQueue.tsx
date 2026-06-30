// The LANDING surface: the risk-ranked queue, NOT the document. Highest risk
// is item #1, never buried. Items are grouped under explicit tier headers; a
// tier with zero items renders as an explicit empty band (not a missing
// section) so Sam can see "nothing high-risk left" as a deliberate state.
//
// The queue arrives already ranked (tier asc, then position). We keep that flat
// order for keyboard nav and number-key selection, and only group for display.

import { QueueItemCard } from "./QueueItemCard";
import { TIERS, TIER_ORDER } from "../lib/review";
import type { ReviewItem, ReviewTier } from "../types/contract";

export function ReviewQueue({
  queue,
  activeId,
  onAccept,
  onFlip,
  onFocus,
}: {
  queue: ReviewItem[];
  activeId: string | null;
  onAccept: (item: ReviewItem) => void;
  onFlip: (item: ReviewItem) => void;
  onFocus: (item: ReviewItem) => void;
}) {
  // Flat 1-based index by queue order, so #N matches the number-key shortcut.
  const indexOf = new Map(queue.map((it, i) => [it.id, i + 1]));
  const byTier = (t: ReviewTier) => queue.filter((it) => it.tier === t);

  return (
    <div className="space-y-5">
      {TIER_ORDER.map((t) => {
        const meta = TIERS[t];
        const items = byTier(t);
        return (
          <section key={t}>
            <header className="mb-2 flex items-baseline gap-2">
              <span
                className={`rounded px-2 py-0.5 text-xs font-bold ${meta.chip}`}
              >
                Tier {t} · {meta.label}
              </span>
              <span className="text-xs text-slate-400">{meta.blurb}</span>
              <span className="ml-auto text-xs font-medium text-slate-400">
                {items.length}
              </span>
            </header>

            {items.length === 0 ? (
              <p className="rounded-lg border border-dashed border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-400">
                No tier-{t} findings.
              </p>
            ) : (
              <div className="space-y-2">
                {items.map((it) => (
                  <QueueItemCard
                    key={it.id}
                    item={it}
                    index={indexOf.get(it.id)!}
                    active={activeId === it.id}
                    onAccept={() => onAccept(it)}
                    onFlip={() => onFlip(it)}
                    onFocus={() => onFocus(it)}
                  />
                ))}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}
