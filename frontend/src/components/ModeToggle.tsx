// REDACT / ANONYMIZE toggle. Lives in the review UI and re-renders the preview
// live (via /preview) WITHOUT re-running detection — flipping it only changes
// how the already-decided spans are rendered.

import type { OutputMode } from "../types/contract";

const MODES: { value: OutputMode; label: string; hint: string }[] = [
  { value: "REDACT", label: "Redact", hint: "black out — [REDACTED]" },
  { value: "ANONYMIZE", label: "Anonymize", hint: "label — [PHONE_1]" },
];

export function ModeToggle({
  mode,
  onChange,
}: {
  mode: OutputMode;
  onChange: (m: OutputMode) => void;
}) {
  return (
    <div className="inline-flex flex-col gap-1">
      <div className="inline-flex overflow-hidden rounded-md border border-slate-300">
        {MODES.map((m) => (
          <button
            key={m.value}
            onClick={() => onChange(m.value)}
            aria-pressed={mode === m.value}
            title={m.hint}
            className={`px-3 py-1.5 text-sm font-medium transition-colors ${
              mode === m.value
                ? "bg-slate-900 text-white"
                : "bg-white text-slate-600 hover:bg-slate-50"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <span className="text-[11px] text-slate-400">
        {MODES.find((m) => m.value === mode)?.hint} · live preview, no re-detect
      </span>
    </div>
  );
}
