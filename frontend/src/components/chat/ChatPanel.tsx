"use client";

import { useEffect, useRef, useState } from "react";
import { useGameStore } from "@/stores/gameStore";
import { MessageBubble } from "./MessageBubble";
import { ChatInput } from "./ChatInput";
import { requestHint, ApiError } from "@/lib/api";

export function ChatPanel() {
  const activeSuspectId = useGameStore((s) => s.activeSuspectId);
  const suspects        = useGameStore((s) => s.suspects);
  const messages        = useGameStore((s) => s.messages);
  const error           = useGameStore((s) => s.error);
  const setError        = useGameStore((s) => s.setError);
  const sessionId       = useGameStore((s) => s.sessionId);
  const phase           = useGameStore((s) => s.phase);
  const hint            = useGameStore((s) => s.hint);
  const setHint         = useGameStore((s) => s.setHint);

  const [hintLoading, setHintLoading] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);

  const activeSuspect  = suspects.find((s) => s.id === activeSuspectId);
  const activeMessages = activeSuspectId ? (messages[activeSuspectId] ?? []) : [];

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [activeMessages.length, activeMessages.at(-1)?.content]);

  const handleHint = async () => {
    if (!sessionId || hintLoading) return;
    setHintLoading(true);
    setHint(null);
    try {
      const res = await requestHint(sessionId);
      setHint(res.hint);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Could not fetch hint.";
      setError(msg);
    } finally {
      setHintLoading(false);
    }
  };

  if (!activeSuspect) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-stone-700 font-mono">
        <div className="text-4xl mb-4 opacity-30">🔍</div>
        <div className="text-sm tracking-wider">Select a suspect to begin</div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">

      {/* ── Header ──────────────────────────────────────────────────────── */}
      <div className="px-6 py-4 border-b border-stone-800/80 shrink-0 flex items-start justify-between">
        <div>
          <div className="text-[10px] text-amber-500/50 tracking-[0.25em] uppercase mb-1">
            Interrogating
          </div>
          <div className="text-stone-100 font-mono font-medium text-base">
            {activeSuspect.name}
          </div>
          <div className="text-[11px] text-stone-400 mt-1 leading-relaxed max-w-lg">
            {activeSuspect.cover_story}
          </div>
        </div>

        {/* Hint button — only during investigation */}
        {phase === "investigation" && (
          <button
            onClick={handleHint}
            disabled={hintLoading}
            title="Get a hint from your informant"
            className="shrink-0 ml-4 mt-1 text-[10px] font-mono px-2.5 py-1.5 border border-stone-700/60 text-stone-600 rounded hover:border-amber-500/40 hover:text-amber-500/70 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {hintLoading ? "…" : "Get Hint"}
          </button>
        )}
      </div>

      {/* ── Hint banner ─────────────────────────────────────────────────── */}
      {hint && (
        <div className="mx-6 mt-3 px-4 py-3 bg-amber-950/20 border border-amber-700/30 rounded flex items-start justify-between gap-3">
          <div>
            <div className="text-[9px] text-amber-500/50 font-mono uppercase tracking-widest mb-1">
              Informant
            </div>
            <p className="text-amber-400/80 text-xs font-mono leading-relaxed italic">
              &ldquo;{hint}&rdquo;
            </p>
          </div>
          <button
            onClick={() => setHint(null)}
            className="text-stone-700 hover:text-stone-500 text-sm shrink-0 mt-0.5"
            aria-label="Dismiss hint"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Error banner ────────────────────────────────────────────────── */}
      {error && (
        <div className="mx-6 mt-3 px-4 py-2.5 bg-red-950/40 border border-red-800/50 rounded text-red-400 text-xs font-mono flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="ml-4 text-red-600 hover:text-red-400"
          >
            ×
          </button>
        </div>
      )}

      {/* ── Message list ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">
        {activeMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center pb-8">
            <div className="text-3xl mb-4 opacity-20">💬</div>
            <div className="text-stone-400 text-sm font-mono">
              {activeSuspect.name} is waiting.
            </div>
            <div className="text-stone-500 text-xs mt-2">
              Ask your first question carefully.
            </div>
          </div>
        ) : (
          activeMessages.map((msg) => (
            <MessageBubble
              key={msg.id}
              message={msg}
              characterName={activeSuspect.name}
            />
          ))
        )}
        <div ref={bottomRef} />
      </div>

      {/* ── Input ───────────────────────────────────────────────────────── */}
      <ChatInput />
    </div>
  );
}
