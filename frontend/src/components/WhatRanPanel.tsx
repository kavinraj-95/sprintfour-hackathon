// Honest "what ran" report. The product NEVER claims a document is clean —
// that rebuilds the over-trust we're fighting. We say which layers ran, which
// were skipped, and how many findings each produced.

import type { LayerStatus } from "../types/contract";

const DOT: Record<string, string> = {
  ok: "bg-emerald-500",
  skipped: "bg-slate-300",
  error: "bg-red-500",
};

export function WhatRanPanel({ layers }: { layers: LayerStatus[] }) {
  const ran = layers.filter((l) => l.status === "ok");
  const skipped = layers.filter((l) => l.status === "skipped");

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold text-slate-700">What ran</h2>
        <span className="text-slate-400">
          {ran.length} ran · {skipped.length} skipped
        </span>
      </div>
      <ul className="space-y-1.5">
        {layers.map((l) => (
          <li key={l.name} className="flex items-start gap-2" title={l.detail}>
            <span
              className={`mt-1 h-2 w-2 shrink-0 rounded-full ${DOT[l.status] ?? "bg-slate-300"}`}
            />
            <span className="flex-1">
              <span className="font-medium uppercase tracking-wide text-slate-600">
                {l.name}
              </span>{" "}
              <span className="text-slate-400">{l.status}</span>
              <span className="block text-slate-400">{l.detail}</span>
            </span>
            <span className="tabular-nums text-slate-500">{l.count}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
