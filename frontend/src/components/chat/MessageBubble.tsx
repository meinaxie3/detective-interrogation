"use client";

import clsx from "clsx";
import type { ChatMessage } from "@/lib/types";

interface Props {
  message: ChatMessage;
  characterName: string;
}

export function MessageBubble({ message, characterName }: Props) {
  const isPlayer = message.role === "player";

  return (
    <div className={clsx("flex w-full", isPlayer ? "justify-end" : "justify-start")}>
      <div
        className={clsx(
          "max-w-[78%] rounded-lg px-4 py-3 text-sm leading-relaxed",
          isPlayer
            ? "bg-slate-800 text-slate-100 rounded-br-none border border-slate-700"
            : "bg-stone-900/80 text-stone-200 rounded-bl-none border border-stone-700/60",
        )}
      >
        {/* Character label above their response */}
        {!isPlayer && (
          <div className="text-[10px] text-amber-500/60 mb-1.5 tracking-[0.2em] uppercase font-mono">
            {characterName}
          </div>
        )}

        {/* Message text */}
        <span className="whitespace-pre-wrap">
          {message.content}
        </span>

        {/* Blinking cursor while streaming */}
        {message.isStreaming && message.content.length === 0 && (
          <span className="inline-block w-2 h-4 bg-amber-500/60 animate-pulse align-middle" />
        )}
        {message.isStreaming && message.content.length > 0 && (
          <span className="streaming-cursor" />
        )}
      </div>
    </div>
  );
}
