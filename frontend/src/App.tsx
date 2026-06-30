import { useCallback, useEffect, useRef, useState } from "react";
import { api, ApiError } from "./api/client";
import { ActionLog, type LogEntry } from "./components/ActionLog";
import { DocumentView } from "./components/DocumentView";
import { ExportControl } from "./components/ExportControl";
import { ModeToggle } from "./components/ModeToggle";
import { PreviewPanel } from "./components/PreviewPanel";
import { ReviewQueue } from "./components/ReviewQueue";
import { Shortcuts } from "./components/Shortcuts";
import { WhatRanPanel } from "./components/WhatRanPanel";
import { SAMPLE_DOCUMENT } from "./lib/sample";
import type {
  ActionRequest,
  OutputMode,
  PiiType,
  PreviewResult,
  ReviewItem,
  ReviewState,
} from "./types/contract";

// Conseal — Sam's correction-review surface.
//
// The whole point: the tool's confident mistakes (a phone number, the SAME
// number twice, left in plain text) are the ones a fast reviewer skims past.
// This UI pulls his eye straight to them. The LANDING surface is the
// risk-ranked queue, not the document; the document is secondary orientation.
//
// State flow: one ReviewState from the server is the source of truth. Every
// gesture POSTs an action and replaces state with the server's response, so the
// counts/gate/queue are never derived twice. Linked duplicates are resolved by
// dispatching one action per linked id (the server resolves one item per call).

type View = "queue" | "document";

export default function App() {
  const [state, setState] = useState<ReviewState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [view, setView] = useState<View>("queue");
  const [mode, setMode] = useState<OutputMode>("REDACT");
  const [preview, setPreview] = useState<PreviewResult | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const logSeq = useRef(0);
  const [draft, setDraft] = useState(SAMPLE_DOCUMENT);

  const sessionId = state?.session_id ?? null;

  function pushLog(verb: string, detail: string) {
    setLog((l) => [{ id: logSeq.current++, verb, detail }, ...l].slice(0, 50));
  }

  // ---- session lifecycle ------------------------------------------------

  async function start(text: string) {
    setError(null);
    setLoading(true);
    try {
      const s = await api.createReview(text, mode, false);
      setState(s);
      setActiveId(s.queue[0]?.id ?? null);
      setLog([]);
      logSeq.current = 0;
      await refreshPreview(s.session_id, mode);
    } catch (e) {
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : String(e));
    } finally {
      setLoading(false);
    }
  }

  const refreshPreview = useCallback(
    async (sid: string, m: OutputMode) => {
      try {
        setPreview(await api.preview(sid, m));
      } catch {
        setPreview(null);
      }
    },
    [],
  );

  // ---- the core gesture: dispatch actions, refresh, re-preview ----------

  const dispatch = useCallback(
    async (actions: ActionRequest[], sid: string, m: OutputMode) => {
      let latest: ReviewState | null = null;
      for (const a of actions) {
        latest = await api.act(sid, a);
      }
      if (latest) setState(latest);
      await refreshPreview(sid, m);
      return latest;
    },
    [refreshPreview],
  );

  // One gesture, one server action. The backend cascades the decision to every
  // linked occurrence and logs it as a SINGLE undoable step, so "fixes N places"
  // fixes all N and one undo reverts all N.
  const accept = useCallback(
    async (item: ReviewItem) => {
      if (!sessionId) return;
      await dispatch([{ type: "accept", target_id: item.id }], sessionId, mode);
      const n = item.linked_count;
      pushLog("Accepted", n > 0 ? `${item.text} (+${n} linked)` : item.text);
    },
    [sessionId, mode, dispatch],
  );

  const flip = useCallback(
    async (item: ReviewItem) => {
      if (!sessionId) return;
      const next = item.status === "dismissed" ? "accept" : "dismiss";
      await dispatch([{ type: next, target_id: item.id }], sessionId, mode);
      const n = item.linked_count;
      pushLog(
        next === "dismiss" ? "Dismissed" : "Re-flagged",
        n > 0 ? `${item.text} (+${n} linked)` : item.text,
      );
    },
    [sessionId, mode, dispatch],
  );

  const undo = useCallback(async () => {
    if (!sessionId) return;
    await dispatch([{ type: "undo" }], sessionId, mode);
    pushLog("Undid", "last action");
  }, [sessionId, mode, dispatch]);

  const markMissed = useCallback(
    async (start: number, end: number, type: PiiType) => {
      if (!sessionId) return;
      const next = await dispatch(
        [{ type: "add_missed", start, end, pii_type: type }],
        sessionId,
        mode,
      );
      const added = next?.queue.find((q) => q.start === start && q.end === end);
      pushLog("Flagged missed", added?.text ?? `${start}–${end}`);
    },
    [sessionId, mode, dispatch],
  );

  // ---- mode toggle: live re-render, never re-detect ---------------------

  async function changeMode(m: OutputMode) {
    setMode(m);
    if (sessionId) await refreshPreview(sessionId, m);
  }

  // ---- keyboard: fast, queue-first navigation ---------------------------

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (!state) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "TEXTAREA" || tag === "INPUT") return;

      const q = state.queue;
      const active = q.find((it) => it.id === activeId) ?? null;
      const idx = active ? q.indexOf(active) : -1;

      if (e.key === "j") {
        setActiveId(q[Math.min(q.length - 1, idx + 1)]?.id ?? activeId);
      } else if (e.key === "k") {
        setActiveId(q[Math.max(0, idx - 1)]?.id ?? activeId);
      } else if (e.key === "a" && active) {
        void accept(active);
      } else if (e.key === "x" && active) {
        void flip(active);
      } else if (e.key === "u") {
        void undo();
      } else if (/^[1-9]$/.test(e.key)) {
        const target = q[Number(e.key) - 1];
        if (target) setActiveId(target.id);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [state, activeId, accept, flip, undo]);

  function jumpTo(item: ReviewItem) {
    setActiveId(item.id);
    setView("queue");
    document
      .querySelector(`[data-queue-anchor]`)
      ?.scrollIntoView({ behavior: "smooth" });
  }

  // ---- landing: not yet loaded -----------------------------------------

  if (!state) {
    return (
      <main className="mx-auto max-w-2xl p-8 font-sans text-slate-800">
        <h1 className="text-2xl font-semibold">Conseal — review the misses</h1>
        <p className="mt-1 text-sm text-slate-500">
          The tool already redacted what it was sure about. This surfaces what it
          left visible — confident mistakes first.
        </p>
        <label className="mt-6 mb-2 block text-sm font-medium">
          Document text
        </label>
        <textarea
          className="mb-3 h-56 w-full rounded border border-slate-300 p-2 font-mono text-sm"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
        <div className="flex gap-2">
          <button
            onClick={() => start(draft)}
            disabled={loading}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            {loading ? "Detecting…" : "Run review"}
          </button>
          <button
            onClick={() => {
              setDraft(SAMPLE_DOCUMENT);
              start(SAMPLE_DOCUMENT);
            }}
            disabled={loading}
            className="rounded border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
          >
            Load sample document
          </button>
        </div>
        {error && (
          <p className="mt-4 rounded bg-red-50 p-2 text-sm text-red-700">
            {error}
          </p>
        )}
      </main>
    );
  }

  // ---- loaded: the review surface --------------------------------------

  const c = state.counts;

  return (
    <main className="mx-auto max-w-6xl p-4 font-sans text-slate-800">
      <header className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="mr-auto">
          <h1 className="text-lg font-semibold">Conseal — review the misses</h1>
          <p className="text-xs text-slate-500">
            {c.pending} pending · {c.accepted} accepted · {c.dismissed} dismissed
            {c.unresolved_high_risk > 0 && (
              <span className="font-semibold text-red-600">
                {" "}
                · {c.unresolved_high_risk} high-risk unresolved
              </span>
            )}
          </p>
        </div>
        <ModeToggle mode={mode} onChange={changeMode} />
        <div className="inline-flex overflow-hidden rounded-md border border-slate-300 text-sm">
          {(["queue", "document"] as View[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 font-medium capitalize ${
                view === v
                  ? "bg-slate-900 text-white"
                  : "bg-white text-slate-600 hover:bg-slate-50"
              }`}
            >
              {v}
            </button>
          ))}
        </div>
        <button
          onClick={() => {
            setState(null);
            setPreview(null);
          }}
          className="text-xs text-slate-400 underline"
        >
          new document
        </button>
      </header>

      <div className="mb-3">
        <Shortcuts />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
        {/* PRIMARY column: the queue (or the secondary document view) */}
        <div data-queue-anchor>
          {view === "queue" ? (
            <ReviewQueue
              queue={state.queue}
              activeId={activeId}
              onAccept={accept}
              onFlip={flip}
              onFocus={(it) => setActiveId(it.id)}
            />
          ) : (
            <DocumentView
              originalText={state.original_text}
              items={state.queue}
              mode={mode}
              onMarkMissed={markMissed}
            />
          )}
        </div>

        {/* SIDEBAR: honest status, preview, export gate, action log */}
        <aside className="space-y-4">
          <WhatRanPanel layers={state.layers} />
          <ExportControl
            key={c.unresolved_high_risk}
            unresolvedHighRisk={c.unresolved_high_risk}
            onExport={(confirm) => api.export(state.session_id, mode, confirm)}
            onJumpTo={jumpTo}
          />
          <PreviewPanel preview={preview} />
          <ActionLog entries={log} onUndo={undo} canUndo={log.length > 0} />
        </aside>
      </div>

      {error && (
        <p className="mt-4 rounded bg-red-50 p-2 text-sm text-red-700">{error}</p>
      )}
    </main>
  );
}
