"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Sparkles, X, Check, Loader2 } from "lucide-react";

interface ComposeBarProps {
  onSend: (content: string) => void;
  onAiSuggest: () => void;
  aiSuggestion: string | null;
  aiLoading: boolean;
}

export function ComposeBar({
  onSend,
  onAiSuggest,
  aiSuggestion,
  aiLoading,
}: ComposeBarProps) {
  const [text, setText] = useState("");
  const [editedSuggestion, setEditedSuggestion] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const suggestionRef = useRef<HTMLTextAreaElement>(null);

  // Sync suggestion text when a new suggestion arrives
  useEffect(() => {
    if (aiSuggestion) {
      setEditedSuggestion(aiSuggestion);
    }
  }, [aiSuggestion]);

  // Auto-resize textarea
  useEffect(() => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 120)}px`;
    }
  }, [text]);

  function handleSend() {
    const trimmed = text.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setText("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleUseSuggestion() {
    const trimmed = editedSuggestion.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setEditedSuggestion("");
  }

  function handleDismissSuggestion() {
    setEditedSuggestion("");
  }

  const showSuggestion = editedSuggestion.length > 0;

  return (
    <div className="border-t border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)]">
      {/* AI Suggestion Draft */}
      {showSuggestion && (
        <div className="px-3 pt-3">
          <div
            className="rounded-lg p-3 border"
            style={{
              backgroundColor: "rgba(16,185,129,0.06)",
              borderColor: "rgba(16,185,129,0.2)",
            }}
          >
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1.5">
                <Sparkles size={12} className="text-[#10B981]" />
                <span className="text-[10px] font-medium text-[#10B981]">
                  AI Suggestion
                </span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={handleUseSuggestion}
                  className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium text-white transition-all"
                  style={{
                    background: "linear-gradient(135deg, #10B981, #059669)",
                  }}
                >
                  <Check size={10} />
                  Use This
                </button>
                <button
                  onClick={handleDismissSuggestion}
                  className="p-1 rounded text-[#6B7280] hover:text-white transition-colors"
                >
                  <X size={12} />
                </button>
              </div>
            </div>
            <textarea
              ref={suggestionRef}
              value={editedSuggestion}
              onChange={(e) => setEditedSuggestion(e.target.value)}
              className="w-full bg-transparent text-sm text-[#E5E7EB] resize-none outline-none leading-relaxed"
              rows={3}
            />
          </div>
        </div>
      )}

      {/* Compose Input */}
      <div className="flex items-end gap-2 px-3 py-3">
        {/* AI Suggest Button */}
        <button
          onClick={onAiSuggest}
          disabled={aiLoading}
          className="flex-shrink-0 p-2 rounded-lg transition-all text-[#B0B8C8] hover:text-[#10B981] hover:bg-[rgba(16,185,129,0.1)] disabled:opacity-50 disabled:cursor-not-allowed"
          title="AI Suggest"
        >
          {aiLoading ? (
            <Loader2 size={18} className="animate-spin text-[#10B981]" />
          ) : (
            <Sparkles size={18} />
          )}
        </button>

        {/* Text Input */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
          rows={1}
          className="flex-1 px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-white placeholder:text-[#6B7280] focus:outline-none focus:border-[#10B981] resize-none leading-relaxed"
        />

        {/* Send Button */}
        <button
          onClick={handleSend}
          disabled={text.trim().length === 0}
          className="flex-shrink-0 p-2 rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed"
          style={{
            background:
              text.trim().length > 0
                ? "linear-gradient(135deg, #10B981, #059669)"
                : "rgba(255,255,255,0.05)",
          }}
        >
          <Send size={18} className="text-white" />
        </button>
      </div>
    </div>
  );
}
