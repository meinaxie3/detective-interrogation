"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import clsx from "clsx";
import { createGame, ApiError } from "@/lib/api";
import { useGameStore } from "@/stores/gameStore";
import { HistoryPanel } from "@/components/history/HistoryPanel";
import type { Difficulty } from "@/lib/types";

type HomeTab = "case" | "history";

const DIFFICULTIES: { id: Difficulty; label: string; desc: string }[] = [
  { id: "easy",   label: "Easy",   desc: "-1 pt / question" },
  { id: "medium", label: "Medium", desc: "-2 pts / question" },
  { id: "hard",   label: "Hard",   desc: "-3 pts / question" },
];

export default function HomePage() {
  const [tab,        setTab]        = useState<HomeTab>("case");
  const [difficulty, setDifficulty] = useState<Difficulty>("medium");
  const [loading,    setLoading]    = useState(false);
  const [error,      setError]      = useState("");

  const { startGame, setDifficulty: storeDifficulty } = useGameStore();
  const router = useRouter();

  const handleStart = async () => {
    setLoading(true);
    setError("");
    try {
      storeDifficulty(difficulty);
      const game = await createGame("manor_1920", difficulty);
      startGame(game);
      router.push(`/game/${game.session_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Server error (${err.status}): ${err.message}`);
      } else {
        setError("Could not reach the case server. Is the backend running on port 8000?");
      }
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-[#060608] flex items-center justify-center px-6 py-10">
      <div className="max-w-md w-full">

        {/* ── Masthead ──────────────────────────────────────────────────── */}
        <div className="text-center mb-8">
          <div className="text-5xl mb-6 select-none" aria-hidden>🔍</div>
          <h1 className="text-2xl font-mono font-bold text-amber-400 tracking-[0.3em] uppercase mb-1">
            Detective Room
          </h1>
          <div className="text-[11px] text-stone-600 tracking-[0.3em] uppercase font-mono">
            Interrogation Suite
          </div>
        </div>

        {/* ── Tab bar ───────────────────────────────────────────────────── */}
        <div className="flex border-b border-stone-800 mb-6">
          {(["case", "history"] as HomeTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={clsx(
                "flex-1 py-2 text-xs font-mono tracking-[0.15em] uppercase transition-colors",
                tab === t
                  ? "text-amber-400 border-b-2 border-amber-500/60 -mb-px"
                  : "text-stone-600 hover:text-stone-400",
              )}
            >
              {t === "case" ? "Case File" : "History"}
            </button>
          ))}
        </div>

        {/* ── Case File tab ──────────────────────────────────────────────── */}
        {tab === "case" && (
          <div>
            {/* Case briefing */}
            <div className="mb-5 p-4 bg-stone-900/40 border border-stone-800 rounded-lg">
              <div className="text-[10px] text-amber-500/50 tracking-[0.2em] uppercase mb-2 font-mono">
                Active Case File
              </div>
              <div className="text-stone-300 font-mono text-sm font-medium mb-1">
                The Ashworth Manor Affair
              </div>
              <div className="text-stone-600 text-xs leading-relaxed font-mono">
                1920 · Lord Edmund Ashworth found dead in his study.
                Poisoned wine. Three people in the house that night.
              </div>
              <div className="mt-3 flex gap-4 text-[10px] font-mono">
                <span className="text-stone-700">3 suspects</span>
                <span className="text-stone-800">·</span>
                <span className="text-stone-700">1 culprit</span>
              </div>
            </div>

            {/* Difficulty selector */}
            <div className="mb-5">
              <div className="text-[10px] text-stone-500 font-mono uppercase tracking-widest mb-2">
                Difficulty
              </div>
              <div className="grid grid-cols-3 gap-2">
                {DIFFICULTIES.map(({ id, label, desc }) => (
                  <button
                    key={id}
                    onClick={() => setDifficulty(id)}
                    className={clsx(
                      "py-2.5 px-3 rounded border text-center transition-all",
                      difficulty === id
                        ? id === "easy"
                          ? "border-emerald-600/60 bg-emerald-950/20 text-emerald-400"
                          : id === "medium"
                            ? "border-amber-500/50 bg-amber-950/20 text-amber-400"
                            : "border-red-700/50 bg-red-950/20 text-red-400"
                        : "border-stone-800 text-stone-600 hover:border-stone-700 hover:text-stone-400",
                    )}
                  >
                    <div className="font-mono text-xs font-medium">{label}</div>
                    <div className="text-[9px] font-mono mt-0.5 opacity-60">{desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="mb-4 px-4 py-3 bg-red-950/40 border border-red-800/40 rounded text-red-400 text-xs font-mono">
                {error}
              </div>
            )}

            {/* Start button */}
            <button
              onClick={handleStart}
              disabled={loading}
              className={clsx(
                "w-full py-3.5 font-mono tracking-[0.2em] uppercase text-sm border rounded transition-all",
                loading
                  ? "bg-stone-900 border-stone-700 text-stone-600 cursor-not-allowed"
                  : "bg-amber-600/10 border-amber-500/40 text-amber-400 hover:bg-amber-600/20 hover:border-amber-500/60",
              )}
            >
              {loading ? "Opening Case File…" : "Begin Investigation"}
            </button>

            <div className="mt-5 text-[10px] text-stone-800 font-mono text-center">
              Powered by Claude · Phase 5
            </div>
          </div>
        )}

        {/* ── History tab ───────────────────────────────────────────────── */}
        {tab === "history" && <HistoryPanel />}
      </div>
    </main>
  );
}
