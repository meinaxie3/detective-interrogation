"use client";

import clsx from "clsx";
import { useGameStore } from "@/stores/gameStore";
import type { ExtractedClue } from "@/lib/types";

// ── Category badge ────────────────────────────────────────────────────────────

const CATEGORY_STYLES: Record<string, string> = {
  location: "bg-blue-950/60   text-blue-400/70   border-blue-800/40",
  time:     "bg-purple-950/60 text-purple-400/70 border-purple-800/40",
  person:   "bg-amber-950/60  text-amber-400/70  border-amber-800/40",
  object:   "bg-stone-900/60  text-stone-400/70  border-stone-700/40",
};

function CategoryBadge({ category }: { category: string }) {
  const style = CATEGORY_STYLES[category] ?? CATEGORY_STYLES.object;
  return (
    <span
      className={clsx(
        "text-[9px] font-mono tracking-widest uppercase px-1.5 py-0.5 rounded border",
        style,
      )}
    >
      {category}
    </span>
  );
}

// ── Single clue card ──────────────────────────────────────────────────────────

function ClueCard({ clue }: { clue: ExtractedClue }) {
  return (
    <div className="px-3 py-2.5 rounded border border-stone-800/60 bg-stone-900/40">
      <div className="flex items-start justify-between gap-2 mb-1">
        <CategoryBadge category={clue.category} />
        <span className="text-[9px] text-stone-700 font-mono shrink-0">
          turn {clue.turn}
        </span>
      </div>
      <p className="text-[11px] text-stone-400 leading-relaxed font-mono">
        {clue.text}
      </p>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

interface EvidenceLockerProps {
  collapsed?: boolean;
  onToggle?: () => void;
}

export function EvidenceLocker({ collapsed = false, onToggle }: EvidenceLockerProps) {
  const evidence = useGameStore((s) => s.evidence);
  const suspects = useGameStore((s) => s.suspects);

  // Group clues by suspect
  const bySuspect: Record<string, ExtractedClue[]> = {};
  for (const clue of evidence) {
    if (!bySuspect[clue.suspect_id]) bySuspect[clue.suspect_id] = [];
    bySuspect[clue.suspect_id].push(clue);
  }

  const getSuspectName = (id: string) =>
    suspects.find((s) => s.id === id)?.name ?? id;

  return (
    <aside
      className={clsx(
        "border-l border-stone-800/80 flex flex-col shrink-0 transition-all duration-200",
        collapsed ? "w-10" : "w-72",
      )}
    >
      {/* Header / toggle */}
      <div
        className="px-3 py-4 border-b border-stone-800/80 flex items-center justify-between cursor-pointer select-none"
        onClick={onToggle}
        role="button"
        aria-label={collapsed ? "Expand evidence locker" : "Collapse evidence locker"}
      >
        {!collapsed && (
          <div className="text-[10px] text-amber-500/50 tracking-[0.25em] uppercase font-mono">
            Evidence
          </div>
        )}
        <span className="text-stone-700 text-xs font-mono ml-auto">
          {collapsed ? "›" : "‹"}
        </span>
      </div>

      {/* Content */}
      {!collapsed && (
        <div className="flex-1 overflow-y-auto p-3 space-y-4">
          {evidence.length === 0 ? (
            <div className="text-center py-8">
              <div className="text-2xl mb-3 opacity-20" aria-hidden>🔍</div>
              <p className="text-[11px] text-stone-500 font-mono leading-relaxed">
                No evidence gathered yet.
              </p>
              <p className="text-[10px] text-stone-600 font-mono mt-1 leading-relaxed">
                Clues surface automatically as suspects speak.
              </p>
            </div>
          ) : (
            Object.entries(bySuspect).map(([suspectId, clues]) => (
              <div key={suspectId}>
                <div className="text-[9px] text-stone-400 font-mono tracking-widest uppercase mb-2">
                  {getSuspectName(suspectId)}
                </div>
                <div className="space-y-2">
                  {clues.map((clue) => (
                    <ClueCard key={clue.clue_id} clue={clue} />
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Collapsed badge count */}
      {collapsed && evidence.length > 0 && (
        <div className="flex-1 flex items-start justify-center pt-4">
          <span className="text-[10px] text-amber-500/50 font-mono writing-vertical">
            {evidence.length}
          </span>
        </div>
      )}
    </aside>
  );
}
