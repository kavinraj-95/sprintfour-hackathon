// Always-visible keyboard legend. Sam is fast and keyboard-first; surfacing the
// gestures keeps the queue navigable without reaching for the mouse.

const KEYS: [string, string][] = [
  ["j / k", "next / prev"],
  ["a", "accept (all linked)"],
  ["x", "dismiss / flip"],
  ["m", "flag selection (doc)"],
  ["u", "undo"],
  ["1–9", "jump to item"],
];

export function Shortcuts() {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-slate-500">
      {KEYS.map(([k, label]) => (
        <span key={k} className="flex items-center gap-1">
          <kbd className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-slate-700 ring-1 ring-slate-200">
            {k}
          </kbd>
          {label}
        </span>
      ))}
    </div>
  );
}
