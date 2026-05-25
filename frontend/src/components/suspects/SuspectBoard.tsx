"use client";

import clsx from "clsx";
import { useGameStore } from "@/stores/gameStore";

// Maximum pressure value used to scale the meter bar.
// Corresponds to the highest pressure_threshold in the scenario (butler = 8)
// plus a buffer; suspects can technically exceed their threshold.
const PRESSURE_MAX = 12;

function PressureMeter({ level }: { level: number }) {
  const pct = Math.min(100, (level / PRESSURE_MAX) * 100);
  const colorClass =
    pct >= 75
      ? "bg-red-600/80"
      : pct >= 45
        ? "bg-amber-500/80"
        : "bg-emerald-700/60";

  if (level === 0) return null;

  return (
    <div className="mt-2">
      <div className="flex items-center justify-between mb-0.5">
        <span className="text-[9px] text-stone-500 font-mono tracking-widest uppercase">
          Pressure
        </span>
        <span className="text-[9px] font-mono text-stone-500">{level}</span>
      </div>
      <div className="h-1 w-full bg-stone-800 rounded-full overflow-hidden">
        <div
          className={clsx("h-full rounded-full transition-all duration-500", colorClass)}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function SuspectBoard() {
  const suspects        = useGameStore((s) => s.suspects);
  const activeSuspectId = useGameStore((s) => s.activeSuspectId);
  const messages        = useGameStore((s) => s.messages);
  const suspectStates   = useGameStore((s) => s.suspectStates);
  const isLoading       = useGameStore((s) => s.isLoading);
  const switchSuspect   = useGameStore((s) => s.switchSuspect);
  const caseBrief       = useGameStore((s) => s.caseBrief);

  return (
    <aside className="w-64 border-r border-stone-800/80 flex flex-col shrink-0">

      {/* Header */}
      <div className="px-4 py-4 border-b border-stone-800/80">
        <div className="text-[10px] text-amber-500/50 tracking-[0.25em] uppercase font-mono">
          Suspects
        </div>
      </div>

      {/* Suspect list */}
      <nav className="flex-1 overflow-y-auto py-1">
        {suspects.map((suspect) => {
          const suspectMessages = messages[suspect.id] ?? [];
          const exchangeCount = suspectMessages.filter(
            (m) => m.role === "character",
          ).length;
          const pressureLevel = suspectStates[suspect.id]?.pressure_level ?? 0;
          const isActive = suspect.id === activeSuspectId;
          const hasBeenQuestioned = exchangeCount > 0;

          return (
            <button
              key={suspect.id}
              onClick={() => !isLoading && switchSuspect(suspect.id)}
              disabled={isLoading && !isActive}
              className={clsx(
                "w-full text-left px-4 py-3.5 border-l-2 transition-all",
                "disabled:cursor-not-allowed",
                isActive
                  ? "bg-stone-900/70 border-amber-500/70 text-stone-100"
                  : "border-transparent text-stone-400 hover:bg-stone-900/40 hover:text-stone-300 hover:border-stone-700",
              )}
            >
              {/* Name */}
              <div className="font-mono text-sm font-medium leading-tight">
                {suspect.name}
              </div>

              {/* Cover story snippet */}
              <div className="text-[11px] mt-1 leading-relaxed line-clamp-2 text-stone-400">
                {suspect.cover_story}
              </div>

              {/* Exchange count badge */}
              {hasBeenQuestioned && (
                <div className="mt-1.5 flex items-center gap-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500/50" />
                  <span className="text-[10px] text-amber-500/50 font-mono">
                    {exchangeCount} {exchangeCount === 1 ? "exchange" : "exchanges"}
                  </span>
                </div>
              )}

              {!hasBeenQuestioned && (
                <div className="mt-1.5">
                  <span className="text-[10px] text-stone-500 font-mono">
                    Not yet questioned
                  </span>
                </div>
              )}

              {/* Pressure meter — only shown once questioned */}
              <PressureMeter level={pressureLevel} />
            </button>
          );
        })}
      </nav>

      {/* ── Case File ─────────────────────────────────────────────────────── */}
      {caseBrief && (
        <div className="border-t border-stone-800/80 px-4 py-4 space-y-2.5">
          <div className="text-[10px] text-amber-500/50 tracking-[0.25em] uppercase font-mono mb-2">
            Case File
          </div>

          <div>
            <div className="text-[9px] text-stone-500 font-mono tracking-widest uppercase">
              Victim
            </div>
            <div className="text-[11px] text-stone-300 font-mono mt-0.5">
              {caseBrief.victim}
            </div>
          </div>

          <div>
            <div className="text-[9px] text-stone-500 font-mono tracking-widest uppercase">
              Location
            </div>
            <div className="text-[11px] text-stone-300 font-mono mt-0.5">
              {caseBrief.location}
            </div>
          </div>

          <div>
            <div className="text-[9px] text-stone-500 font-mono tracking-widest uppercase">
              Time of Death
            </div>
            <div className="text-[11px] text-stone-300 font-mono mt-0.5">
              {caseBrief.time_of_death}
            </div>
          </div>

          {caseBrief.setting && (
            <div>
              <div className="text-[9px] text-stone-500 font-mono tracking-widest uppercase">
                Briefing
              </div>
              <div className="text-[10px] text-stone-400 font-mono mt-0.5 leading-relaxed">
                {caseBrief.setting}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Footer hint */}
      {!caseBrief && (
        <div className="px-4 py-3 border-t border-stone-800/60">
          <div className="text-[10px] text-stone-600 font-mono leading-relaxed">
            Each suspect has their own memory. Switch freely.
          </div>
        </div>
      )}
    </aside>
  );
}
