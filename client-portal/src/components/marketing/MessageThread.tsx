"use client";

import { useEffect, useRef } from "react";
import { Bot, Loader2 } from "lucide-react";

interface Message {
  id: string;
  direction: "inbound" | "outbound";
  content: string;
  content_type: string;
  ai_generated: boolean | null;
  human_override: boolean | null;
  created_at: string;
}

interface MessageThreadProps {
  messages: Message[];
  loading: boolean;
}

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  const isYesterday = date.toDateString() === yesterday.toDateString();

  const time = date.toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

  if (isToday) return time;
  if (isYesterday) return `Yesterday ${time}`;

  return `${date.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
  })} ${time}`;
}

function shouldShowDateSeparator(
  current: Message,
  previous: Message | undefined
): boolean {
  if (!previous) return true;
  const currentDate = new Date(current.created_at).toDateString();
  const previousDate = new Date(previous.created_at).toDateString();
  return currentDate !== previousDate;
}

function getDateLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();

  if (date.toDateString() === now.toDateString()) return "Today";

  const yesterday = new Date(now);
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";

  return date.toLocaleDateString("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
  });
}

export function MessageThread({ messages, loading }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (loading) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={24} className="animate-spin text-[#10B981]" />
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-sm text-[#6B7280]">No messages in this conversation yet.</p>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="flex-1 overflow-y-auto px-4 py-4 space-y-1"
    >
      {messages.map((msg, idx) => {
        const prevMsg = idx > 0 ? messages[idx - 1] : undefined;
        const showDate = shouldShowDateSeparator(msg, prevMsg);
        const isInbound = msg.direction === "inbound";

        return (
          <div key={msg.id}>
            {/* Date separator */}
            {showDate && (
              <div className="flex items-center justify-center py-3">
                <span className="text-[10px] text-[#6B7280] bg-[rgba(255,255,255,0.03)] px-3 py-1 rounded-full">
                  {getDateLabel(msg.created_at)}
                </span>
              </div>
            )}

            {/* Message bubble */}
            <div
              className={`flex mb-1.5 ${
                isInbound ? "justify-start" : "justify-end"
              }`}
            >
              <div
                className={`relative max-w-[75%] rounded-xl px-3.5 py-2.5 ${
                  isInbound ? "rounded-bl-sm" : "rounded-br-sm"
                }`}
                style={{
                  backgroundColor: isInbound
                    ? "rgba(255,255,255,0.05)"
                    : "rgba(16,185,129,0.15)",
                }}
              >
                {/* AI label */}
                {msg.ai_generated && (
                  <div className="flex items-center gap-1 mb-1">
                    <Bot size={10} className="text-[#10B981]" />
                    <span className="text-[9px] font-medium text-[#10B981]">
                      AI{msg.human_override ? " (edited)" : ""}
                    </span>
                  </div>
                )}

                {/* Content */}
                <p
                  className={`text-sm leading-relaxed whitespace-pre-wrap break-words ${
                    isInbound ? "text-[#E5E7EB]" : "text-white"
                  }`}
                >
                  {msg.content}
                </p>

                {/* Timestamp */}
                <p
                  className={`text-[10px] mt-1 ${
                    isInbound ? "text-[#6B7280]" : "text-[rgba(255,255,255,0.5)]"
                  }`}
                >
                  {formatTimestamp(msg.created_at)}
                </p>
              </div>
            </div>
          </div>
        );
      })}
      <div ref={bottomRef} />
    </div>
  );
}
