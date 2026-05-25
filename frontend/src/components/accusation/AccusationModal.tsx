"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { useGameStore } from "@/stores/gameStore";
import { submitAccusation, ApiError } from "@/lib/api";
import type { AccuseResponse } from "@/lib/types";

interface AccusationModalProps {
  onClose: () => void;
}

// ── Resolution screen (shown after accusation resolves) ───────────────────────

function ResolutionScreen({
  result,
  onNewGame,
}: {
  result: AccuseResponse;
  onNewGame: () => void;
}) {
  return (
    <div className="flex flex-col gap-6">
      {/* Verdict banner */}
      <div
        className={clsx(
          "rounded-lg px-5 py-4 border text-center",
          result.is_correct
            ? "bg-emerald-950/40 border-emerald-700/40"
            : "bg-red-950/40 border-red-800/40",
        )}
      >
        <div className="text-2xl mb-2" aria-hidden>
          {result.is_correct ? "✓" : "✗"}
        </div>
        <div
          className={clsx(
            "font-mono text-sm font-bold tracking-wider uppercase",
            result.is_correct ? "text-emerald-400" : "text-red-400",
          )}
        >
          {result.is_correct ? "Correct — Case Closed" : "Wrong — Case Closed"}
        </div>
        <div className="text-xs text-stone-500 font-mono mt-1">
          Score: {result.score}
        </div>
      </div>

      {/* True facts */}
      <div className="space-y-3">
        <div className="text-[10px] text-amber-500/50 tracking-[0.2em] uppercase font-mono">
          The Truth
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-stone-900/40 border border-stone-800 rounded p-3">
            <div className="text-[9px] text-stone-600 font-mono uppercase tracking-widest mb-1">Culprit</div>
            <div className="text-xs text-stone-300 font-mono">{result.correct_culprit_id}</div>
          </div>
          <div className="bg-stone-900/40 border border-stone-800 rounded p-3">
            <div className="text-[9px] text-stone-600 font-mono uppercase tracking-widest mb-1">Method</div>
            <div className="text-xs text-stone-300 font-mono">{result.correct_method}</div>
          </div>
        </div>
        <div className="bg-stone-900/40 border border-stone-800 rounded p-3">
          <div className="text-[9px] text-stone-600 font-mono uppercase tracking-widest mb-1">True Motive</div>
          <div className="text-xs text-stone-400 font-mono leading-relaxed">{result.correct_motive}</div>
        </div>
      </div>

      {/* Narrative */}
      <div className="space-y-2">
        <div className="text-[10px] text-amber-500/50 tracking-[0.2em] uppercase font-mono">
          Resolution
        </div>
        <p className="text-xs text-stone-500 font-mono leading-relaxed bg-stone-900/30 rounded border border-stone-800/60 p-3">
          {result.resolution_narrative}
        </p>
      </div>

      {/* New game */}
      <button
        onClick={onNewGame}
        className="w-full py-3 font-mono tracking-[0.2em] uppercase text-sm border rounded transition-all bg-amber-600/10 border-amber-500/40 text-amber-400 hover:bg-amber-600/20 hover:border-amber-500/60"
      >
        New Investigation
      </button>
    </div>
  );
}

// ── Accusation form ───────────────────────────────────────────────────────────

export function AccusationModal({ onClose }: AccusationModalProps) {
  const router  = useRouter();
  const { sessionId, suspects, setAccusationResult, accusationResult } = useGameStore();

  const [suspectId, setSuspectId] = useState(suspects[0]?.id ?? "");
  const [motive,    setMotive]    = useState("");
  const [method,    setMethod]    = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError,  setFormError]  = useState("");

  const handleSubmit = async () => {
    if (!suspectId || !motive.trim() || !method.trim()) {
      setFormError("All three fields are required.");
      return;
    }
    if (!sessionId) return;

    setSubmitting(true);
    setFormError("");

    try {
      const result = await submitAccusation({
        session_id: sessionId,
        suspect_id: suspectId,
        motive:     motive.trim(),
        method:     method.trim(),
      });
      setAccusationResult(result);
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : "Could not submit accusation. Please try again.";
      setFormError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleNewGame = () => {
    useGameStore.getState().reset();
    router.push("/");
  };

  return (
    // Backdrop
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm"
      onClick={(e) => {
        if (e.target === e.currentTarget && !accusationResult) onClose();
      }}
    >
      {/* Modal panel */}
      <div className="relative w-full max-w-md mx-4 bg-[#070709] border border-stone-800 rounded-xl shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="px-6 py-5 border-b border-stone-800/80 flex items-center justify-between">
          <div>
            <div className="text-[10px] text-amber-500/50 tracking-[0.2em] uppercase font-mono mb-0.5">
              Final Accusation
            </div>
            <div className="text-stone-200 font-mono font-medium text-sm">
              {accusationResult ? "Case Resolved" : "Name Your Culprit"}
            </div>
          </div>
          {!accusationResult && (
            <button
              onClick={onClose}
              className="text-stone-700 hover:text-stone-500 font-mono text-lg transition-colors"
              aria-label="Close"
            >
              ×
            </button>
          )}
        </div>

        {/* Body */}
        <div className="px-6 py-5">
          {accusationResult ? (
            <ResolutionScreen result={accusationResult} onNewGame={handleNewGame} />
          ) : (
            <div className="space-y-5">
              <p className="text-xs text-stone-600 font-mono leading-relaxed">
                This is irreversible. Choose carefully — you have one shot.
              </p>

              {/* Suspect selector */}
              <div>
                <label className="block text-[10px] text-stone-500 font-mono uppercase tracking-widest mb-1.5">
                  Accused Suspect
                </label>
                <select
                  value={suspectId}
                  onChange={(e) => setSuspectId(e.target.value)}
                  className="w-full bg-stone-900/60 border border-stone-700 rounded px-3 py-2.5 text-stone-300 font-mono text-sm focus:outline-none focus:border-amber-500/50 transition-colors"
                >
                  {suspects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Motive */}
              <div>
                <label className="block text-[10px] text-stone-500 font-mono uppercase tracking-widest mb-1.5">
                  Stated Motive
                </label>
                <input
                  type="text"
                  value={motive}
                  onChange={(e) => setMotive(e.target.value)}
                  placeholder="Why did they do it?"
                  className="w-full bg-stone-900/60 border border-stone-700 rounded px-3 py-2.5 text-stone-300 font-mono text-sm placeholder-stone-700 focus:outline-none focus:border-amber-500/50 transition-colors"
                />
              </div>

              {/* Method */}
              <div>
                <label className="block text-[10px] text-stone-500 font-mono uppercase tracking-widest mb-1.5">
                  Method Used
                </label>
                <input
                  type="text"
                  value={method}
                  onChange={(e) => setMethod(e.target.value)}
                  placeholder="How was it done?"
                  className="w-full bg-stone-900/60 border border-stone-700 rounded px-3 py-2.5 text-stone-300 font-mono text-sm placeholder-stone-700 focus:outline-none focus:border-amber-500/50 transition-colors"
                />
              </div>

              {/* Error */}
              {formError && (
                <div className="px-3 py-2 bg-red-950/40 border border-red-800/40 rounded text-red-400 text-xs font-mono">
                  {formError}
                </div>
              )}

              {/* Submit */}
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className={clsx(
                  "w-full py-3 font-mono tracking-[0.2em] uppercase text-sm border rounded transition-all",
                  submitting
                    ? "bg-stone-900 border-stone-700 text-stone-600 cursor-not-allowed"
                    : "bg-red-950/20 border-red-800/40 text-red-400 hover:bg-red-950/40 hover:border-red-700/60",
                )}
              >
                {submitting ? "Submitting…" : "Make Accusation"}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
