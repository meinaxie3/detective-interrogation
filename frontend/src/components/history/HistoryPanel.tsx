"use client";

import { useEffect, useState } from "react";
import clsx from "clsx";
import { getHistory } from "@/lib/api";
import type { GameRecord } from "@/lib/types";

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function difficultyLabel(d: string) {
  const map: Record<string, { label: string; cls: string }> = {
    easy:   { label: "Easy",   cls: "text-emerald-500/70" },
    medium: { label: "Medium", cls: "text-amber-500/70"   },
    hard:   { label: "Hard",   cls: "text-red-500/70"     },
  };
  return map[d] ?? { label: d, cls: "text-stone-500" };
}

// ── Component ─────────────────────────────────────────────────────────────────

export function HistoryPanel() {
  const [records, setRecords] = useState<GameRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  useEffect(() => {
    getHistory()
      .then(setRecords)
      .catch(() => setError("Could not load history."))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="text-center py-16 text-stone-700 font-mono text-sm">
        Loading case history…
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-16 text-red-700 font-mono text-sm">
        {error}
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="text-center py-16">
        <div className="text-4xl mb-4 opacity-20">📁</div>
        <div className="text-stone-600 font-mono text-sm">No completed cases yet.</div>
        <div className="text-stone-700 font-mono text-xs mt-2">
          Start an investigation to build your record.
        </div>
      </div>
    );
  }

  return (
    <div className="w-full">
      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3 mb-6">
        {[
          {
            label: "Cases",
            value: records.length,
            cls: "text-stone-300",
          },
          {
            label: "Solved",
            value: records.filter((r) => r.is_correct).length,
            cls: "text-emerald-400",
          },
          {
            label: "Best Score",
            value: Math.max(...records.map((r) => r.score)),
            cls: "text-amber-400",
          },
        ].map(({ label, value, cls }) => (
          <div
            key={label}
            className="bg-stone-900/40 border border-stone-800 rounded-lg p-3 text-center"
          >
            <div className={clsx("text-xl font-mono font-bold", cls)}>{value}</div>
            <div className="text-[10px] text-stone-600 font-mono uppercase tracking-widest mt-0.5">
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Records list */}
      <div className="space-y-2">
        {records.map((r) => {
          const diff = difficultyLabel(r.difficulty);
          return (
            <div
              key={r.record_id}
              className={clsx(
                "rounded-lg border px-4 py-3 flex items-center gap-4",
                r.is_correct
                  ? "border-emerald-900/40 bg-emerald-950/10"
                  : "border-stone-800/60 bg-stone-900/20",
              )}
            >
              {/* Verdict icon */}
              <div className={clsx(
                "text-lg shrink-0",
                r.is_correct ? "text-emerald-500" : "text-red-700",
              )}>
                {r.is_correct ? "✓" : "✗"}
              </div>

              {/* Main info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-stone-300 font-mono text-xs font-medium">
                    {r.accused_suspect_id}
                  </span>
                  <span className="text-stone-700 text-[10px]">→</span>
                  <span className={clsx("text-[10px] font-mono", diff.cls)}>
                    {diff.label}
                  </span>
                  <span className="text-stone-700 text-[10px]">·</span>
                  <span className="text-stone-600 text-[10px] font-mono">
                    {r.total_questions}Q
                  </span>
                </div>
                <div className="text-stone-600 text-[10px] font-mono mt-0.5 truncate">
                  {r.player_motive || "—"}
                </div>
              </div>

              {/* Score */}
              <div className="text-right shrink-0">
                <div className={clsx(
                  "font-mono text-sm font-bold",
                  r.score >= 70 ? "text-amber-400" : r.score >= 40 ? "text-stone-400" : "text-stone-600",
                )}>
                  {r.score}
                </div>
                <div className="text-[9px] text-stone-700 font-mono">pts</div>
              </div>

              {/* Date */}
              <div className="text-[9px] text-stone-700 font-mono shrink-0 text-right hidden sm:block">
                {formatDate(r.timestamp)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
