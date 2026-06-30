// Live output preview — exactly what would be shared. Re-renders whenever the
// mode toggles or a decision changes, by calling /preview (NEVER re-detecting).
// The legend is the share-safe key: it names WHAT was removed, not the value.

import type { PreviewResult } from "../types/contract";

export function PreviewPanel({ preview }: { preview: PreviewResult | null }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="flex items-center justify-between border-b border-slate-100 px-3 py-2">
        <h2 className="text-sm font-semibold text-slate-700">Output preview</h2>
        <span className="text-[11px] text-slate-400">
          what gets shared · no re-detection
        </span>
      </header>
      {!preview ? (
        <p className="px-4 py-3 text-xs text-slate-400">No preview yet.</p>
      ) : (
        <>
          <pre className="max-h-[40vh] overflow-y-auto whitespace-pre-wrap px-4 py-3 font-mono text-[13px] leading-relaxed text-slate-800">
            {preview.output_text}
          </pre>
          <div className="border-t border-slate-100 px-4 py-2">
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-slate-500">
              Legend ({preview.legend.length})
            </h3>
            {preview.legend.length === 0 ? (
              <p className="text-xs text-slate-400">
                Nothing acted on yet — accept items to populate the output.
              </p>
            ) : (
              <ul className="flex flex-wrap gap-1.5">
                {preview.legend.map((e) => (
                  <li
                    key={e.token}
                    className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600"
                  >
                    <span className="font-mono font-medium">{e.token}</span> ·{" "}
                    {e.type} ×{e.occurrences}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  );
}
