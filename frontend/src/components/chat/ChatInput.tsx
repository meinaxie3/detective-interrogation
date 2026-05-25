"use client";

import { useState, useRef, type KeyboardEvent } from "react";
import { useChat } from "@/hooks/useChat";
import { useGameStore } from "@/stores/gameStore";

export function ChatInput() {
  const [input, setInput] = useState("");
  const { sendMessage } = useChat();
  const isLoading = useGameStore((s) => s.isLoading);
  const activeSuspectId = useGameStore((s) => s.activeSuspectId);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const canSend = input.trim().length > 0 && !isLoading && !!activeSuspectId;

  const handleSend = async () => {
    if (!canSend) return;
    const msg = input;
    setInput("");
    // Reset textarea height
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    await sendMessage(msg);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // Send on Enter, newline on Shift+Enter
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleInput = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
  };

  return (
    <div className="border-t border-stone-800/80 p-4 bg-stone-950/50">
      <div className="flex gap-3 items-end">
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          onInput={handleInput}
          disabled={isLoading || !activeSuspectId}
          placeholder={
            activeSuspectId
              ? "Ask your question… (Enter to send)"
              : "Select a suspect to begin"
          }
          rows={1}
          className={`
            flex-1 resize-none overflow-hidden
            bg-stone-900 border border-stone-700/60 rounded-lg
            px-4 py-2.5 text-sm text-stone-200
            placeholder:text-stone-600 font-mono
            focus:outline-none focus:border-amber-500/40
            disabled:opacity-40 disabled:cursor-not-allowed
            transition-colors
          `}
        />
        <button
          onClick={handleSend}
          disabled={!canSend}
          className={`
            px-4 py-2.5 rounded-lg text-sm font-mono tracking-wide
            border transition-all shrink-0
            ${canSend
              ? "bg-amber-600/15 border-amber-500/40 text-amber-400 hover:bg-amber-600/25 hover:border-amber-500/60"
              : "bg-stone-900 border-stone-800 text-stone-700 cursor-not-allowed"
            }
          `}
        >
          {isLoading ? (
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 animate-bounce [animation-delay:0ms]" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 animate-bounce [animation-delay:150ms]" />
              <span className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 animate-bounce [animation-delay:300ms]" />
            </span>
          ) : (
            "Ask →"
          )}
        </button>
      </div>

      <div className="text-[10px] text-stone-500 mt-2 font-mono">
        Enter to send · Shift+Enter for new line
      </div>
    </div>
  );
}
