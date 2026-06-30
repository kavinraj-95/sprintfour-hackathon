import { useEffect, useState } from "react";
import { api, ApiError, type Health } from "./api/client";
import type { SessionState } from "./types/contract";

// Scaffold-level UI: just enough to prove the typed seam is live end-to-end —
// the health probe and a round-trip through /api/session. The review surface
// (document rendering, the missed-PII queue, one-key corrections) is built in
// later layers; this page intentionally has none of it yet.
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState(
    "Call Margaret Holloway on 0412 887 905 about policy 88341-AC.",
  );
  const [session, setSession] = useState<SessionState | null>(null);

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch((e: ApiError) => setError(e.message));
  }, []);

  async function startSession() {
    setError(null);
    try {
      setSession(await api.initSession(text));
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e));
    }
  }

  return (
    <main className="mx-auto max-w-2xl p-8 font-sans text-slate-800">
      <header className="mb-6">
        <h1 className="text-2xl font-semibold">Conseal</h1>
        <p className="text-sm text-slate-500">
          Redaction correction — scaffold. Contract is live; detection comes next.
        </p>
      </header>

      <div className="mb-6 flex items-center gap-2 text-sm">
        <span className="font-medium">Backend:</span>
        {health ? (
          <span className="rounded bg-emerald-100 px-2 py-0.5 text-emerald-700">
            ok · detector={health.detector}
          </span>
        ) : (
          <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-500">
            connecting…
          </span>
        )}
      </div>

      <label className="mb-2 block text-sm font-medium">Document text</label>
      <textarea
        className="mb-3 h-28 w-full rounded border border-slate-300 p-2 text-sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        onClick={startSession}
      >
        Start review session
      </button>

      {error && (
        <p className="mt-4 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>
      )}

      {session && (
        <section className="mt-6 rounded border border-slate-200 p-4 text-sm">
          <div className="mb-2 font-medium">Session created</div>
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-slate-600">
            <dt className="text-slate-400">session_id</dt>
            <dd className="font-mono text-xs">{session.session_id}</dd>
            <dt className="text-slate-400">spans</dt>
            <dd>{session.spans.length} (none yet — detection is a later layer)</dd>
            <dt className="text-slate-400">output_mode</dt>
            <dd>{session.output_mode}</dd>
          </dl>
        </section>
      )}
    </main>
  );
}
