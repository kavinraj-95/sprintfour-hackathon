// The export gate — the ONE deliberate friction point, placed at the very last
// step where final-step complacency bites hardest. It is NOT a blocking modal
// (modals get reflexively dismissed). Instead the control itself changes state
// inline:
//
//   clean path   -> single "Export" button.
//   gated path   -> button reads "N unresolved — review first"; pressing it
//                   does NOT export. It reveals the unresolved high-risk items
//                   IN PLACE and arms a second, separate "Export anyway"
//                   action. Only that second deliberate press confirms.
//
// State machine: idle -> (gated) armed -> confirmed | (clean) done.

import { useState } from "react";
import type { ExportResult, ReviewItem } from "../types/contract";

type Phase = "idle" | "armed" | "done";

export function ExportControl({
  unresolvedHighRisk,
  onExport,
  onJumpTo,
}: {
  unresolvedHighRisk: number;
  // Calls /export; confirm=false first, confirm=true on the second press.
  onExport: (confirm: boolean) => Promise<ExportResult>;
  onJumpTo: (item: ReviewItem) => void;
}) {
  const [phase, setPhase] = useState<Phase>("idle");
  const [result, setResult] = useState<ExportResult | null>(null);
  const [busy, setBusy] = useState(false);

  const gated = unresolvedHighRisk > 0;

  async function firstPress() {
    setBusy(true);
    try {
      const res = await onExport(false);
      setResult(res);
      // Server is the authority on the gate, not just our local count.
      setPhase(res.gated ? "armed" : "done");
    } finally {
      setBusy(false);
    }
  }

  async function confirmPress() {
    setBusy(true);
    try {
      const res = await onExport(true);
      setResult(res);
      setPhase("done");
    } finally {
      setBusy(false);
    }
  }

  // Reset the gate whenever the underlying risk count changes out from under us
  // (e.g. Sam resolves an item after arming) — handled by keying in the parent.

  if (phase === "done" && result && !result.gated) {
    return (
      <section className="rounded-lg border border-emerald-300 bg-emerald-50 p-3">
        <div className="mb-1 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-emerald-800">Exported</h2>
          <button
            onClick={() => {
              setPhase("idle");
              setResult(null);
            }}
            className="text-xs text-emerald-700 underline"
          >
            export again
          </button>
        </div>
        <p className="text-xs text-emerald-700">
          {result.legend.length} entit
          {result.legend.length === 1 ? "y" : "ies"} acted on. Output ready to
          share.
        </p>
      </section>
    );
  }

  return (
    <section
      className={`rounded-lg border p-3 ${
        gated ? "border-red-300 bg-red-50" : "border-slate-300 bg-white"
      }`}
    >
      {!gated ? (
        <button
          onClick={firstPress}
          disabled={busy}
          className="w-full rounded bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700 disabled:opacity-50"
        >
          {busy ? "Exporting…" : "Export"}
        </button>
      ) : phase !== "armed" ? (
        <button
          onClick={firstPress}
          disabled={busy}
          className="w-full rounded bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50"
        >
          {unresolvedHighRisk} high-risk unresolved — review first
        </button>
      ) : (
        <div>
          <h2 className="mb-1 text-sm font-semibold text-red-800">
            {(result?.unresolved.length ?? unresolvedHighRisk)} high-risk item
            {unresolvedHighRisk === 1 ? "" : "s"} still visible
          </h2>
          <p className="mb-2 text-xs text-red-700">
            These would leak if you export now. Resolve them, or confirm a
            deliberate override.
          </p>
          <ul className="mb-3 space-y-1">
            {result?.unresolved.map((it) => (
              <li key={it.id}>
                <button
                  onClick={() => onJumpTo(it)}
                  className="w-full truncate rounded border border-red-200 bg-white px-2 py-1 text-left text-xs text-slate-700 hover:border-red-400"
                  title={it.reason}
                >
                  <span className="font-mono font-medium text-red-700">
                    {it.text}
                  </span>{" "}
                  <span className="text-slate-400">— {it.sentence}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="flex gap-2">
            <button
              onClick={() => setPhase("idle")}
              className="flex-1 rounded border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
            >
              Go review them
            </button>
            <button
              onClick={confirmPress}
              disabled={busy}
              className="flex-1 rounded bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-500 disabled:opacity-50"
            >
              {busy ? "Exporting…" : "Export anyway"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
