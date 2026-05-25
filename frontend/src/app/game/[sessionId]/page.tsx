"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useGameStore } from "@/stores/gameStore";
import { SuspectBoard }    from "@/components/suspects/SuspectBoard";
import { ChatPanel }       from "@/components/chat/ChatPanel";
import { EvidenceLocker }  from "@/components/evidence/EvidenceLocker";
import { AccusationModal } from "@/components/accusation/AccusationModal";
import { getSession } from "@/lib/api";

export default function GamePage() {
  const params  = useParams<{ sessionId: string }>();
  const router  = useRouter();

  const {
    sessionId, scenarioTitle, suspects, phase, evidence,
    startGame, setSuspectStates, setPhase, setCaseBrief,
    caseBrief,
  } = useGameStore();

  const [showAccusation,    setShowAccusation]    = useState(false);
  const [evidenceCollapsed, setEvidenceCollapsed] = useState(false);

  // ── Rehydrate on hard reload ───────────────────────────────────────────────
  useEffect(() => {
    if (sessionId) return; // Already in store

    const id = params.sessionId;
    if (!id) {
      router.replace("/");
      return;
    }

    getSession(id)
      .then((data) => {
        startGame({
          session_id:     id,
          scenario_title: data.case_brief.scenario_title,
          setting:        data.case_brief.setting,
          suspects:       data.suspects,
          case_brief:     data.case_brief,
        });
        // Restore case brief for sidebar display
        setCaseBrief(data.case_brief);
        // Restore server-authoritative pressure levels
        if (data.session.suspect_states) {
          setSuspectStates(data.session.suspect_states);
        }
        // Restore phase (may already be resolved)
        if (data.session.phase) {
          setPhase(data.session.phase);
        }
        // Re-open accusation modal if game was already resolved
        if (data.session.phase === "resolved") {
          setShowAccusation(true);
        }
      })
      .catch(() => {
        router.replace("/");
      });
  }, [params.sessionId, sessionId, router, startGame, setSuspectStates, setPhase, setCaseBrief]);

  // ── Loading state ──────────────────────────────────────────────────────────
  if (!sessionId || suspects.length === 0) {
    return (
      <div className="min-h-screen bg-[#060608] flex items-center justify-center">
        <div className="text-stone-700 font-mono text-sm tracking-wider">
          Retrieving case file…
        </div>
      </div>
    );
  }

  const isResolved = phase === "resolved";

  return (
    <div className="flex flex-col h-screen bg-[#060608] overflow-hidden">

      {/* ── Case header ─────────────────────────────────────────────────── */}
      <header className="border-b border-stone-800/80 px-6 py-3 flex items-center justify-between shrink-0 scanline">
        <div>
          <div className="text-[10px] text-amber-500/50 tracking-[0.2em] uppercase font-mono mb-0.5">
            Active Investigation
          </div>
          <div className="text-stone-200 font-mono font-medium text-sm">
            {scenarioTitle}
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Evidence count shortcut */}
          {evidence.length > 0 && (
            <button
              onClick={() => setEvidenceCollapsed(false)}
              className="text-[10px] text-amber-500/40 font-mono hover:text-amber-500/70 transition-colors"
            >
              {evidence.length} clue{evidence.length !== 1 ? "s" : ""}
            </button>
          )}

          <div className="text-[10px] text-stone-700 font-mono">
            {params.sessionId?.slice(0, 8)}
          </div>

          {/* Make Accusation — hidden once resolved */}
          {!isResolved && (
            <button
              onClick={() => setShowAccusation(true)}
              className="text-[11px] font-mono px-3 py-1.5 border border-red-800/40 text-red-500/70 rounded hover:bg-red-950/20 hover:border-red-700/50 hover:text-red-400 transition-all tracking-wide"
            >
              Make Accusation
            </button>
          )}

          {isResolved && (
            <span className="text-[11px] font-mono text-stone-600 tracking-wide">
              Case closed
            </span>
          )}

          <button
            onClick={() => router.push("/")}
            className="text-[11px] text-stone-700 hover:text-stone-500 font-mono transition-colors"
          >
            New Case
          </button>
        </div>
      </header>

      {/* ── Main layout ─────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        <SuspectBoard />
        <ChatPanel />
        <EvidenceLocker
          collapsed={evidenceCollapsed}
          onToggle={() => setEvidenceCollapsed((v) => !v)}
        />
      </div>

      {/* ── Accusation modal (overlay) ───────────────────────────────────── */}
      {showAccusation && (
        <AccusationModal onClose={() => setShowAccusation(false)} />
      )}
    </div>
  );
}
