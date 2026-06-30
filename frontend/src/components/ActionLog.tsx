// A FLAT action log — not a navigable timeline. Its job is reassurance: a slip
// is visible and reversible (undo pops the most recent entry), so Sam moves
// fast without fear that a stray keypress silently destroyed a correction.

export interface LogEntry {
  id: number;
  verb: string; // "Accepted", "Dismissed", "Flagged missed", "Undid"
  detail: string; // the value / context
}

export function ActionLog({
  entries,
  onUndo,
  canUndo,
}: {
  entries: LogEntry[];
  onUndo: () => void;
  canUndo: boolean;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-3 text-xs">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="font-semibold text-slate-700">Action log</h2>
        <button
          onClick={onUndo}
          disabled={!canUndo}
          className="rounded border border-slate-300 px-2 py-0.5 font-medium text-slate-700 enabled:hover:bg-slate-50 disabled:opacity-40"
        >
          Undo (u)
        </button>
      </div>
      {entries.length === 0 ? (
        <p className="text-slate-400">No actions yet.</p>
      ) : (
        <ol className="max-h-40 space-y-1 overflow-y-auto">
          {entries.map((e) => (
            <li key={e.id} className="flex gap-2">
              <span className="font-medium text-slate-600">{e.verb}</span>
              <span className="truncate text-slate-400">{e.detail}</span>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
