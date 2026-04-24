"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { ArrowLeft, Loader2, MessageCircle } from "lucide-react";

import { ConversationList } from "@/components/marketing/ConversationList";
import { MessageThread } from "@/components/marketing/MessageThread";
import { ComposeBar } from "@/components/marketing/ComposeBar";
import { PageHeader } from "@/components/portal/PageHeader";

interface ConversationLead {
  first_name: string | null;
  last_name: string | null;
  email: string | null;
}

interface Conversation {
  id: string;
  channel: string;
  subject: string | null;
  status: string;
  last_message_at: string | null;
  last_message_preview: string | null;
  unread_count: number;
  created_at: string;
  lead: ConversationLead | null;
}

interface Message {
  id: string;
  direction: "inbound" | "outbound";
  content: string;
  content_type: string;
  ai_generated: boolean | null;
  human_override: boolean | null;
  created_at: string;
}

export default function ConversationsPage() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loadingConversations, setLoadingConversations] = useState(true);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [channelFilter, setChannelFilter] = useState<string | null>(null);
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [mobileShowThread, setMobileShowThread] = useState(false);

  const refreshIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ------- Fetch Conversations -------
  const loadConversations = useCallback(async () => {
    const params = new URLSearchParams();
    params.set("limit", "50");
    if (channelFilter) {
      params.set("channel", channelFilter);
    }

    try {
      const res = await fetch(
        `/api/portal/marketing/conversations?${params.toString()}`
      );
      if (res.ok) {
        const body = await res.json();
        setConversations(body.data ?? []);
      }
    } catch {
      // silently fail on poll errors
    } finally {
      setLoadingConversations(false);
    }
  }, [channelFilter]);

  useEffect(() => {
    setLoadingConversations(true);
    loadConversations();
  }, [loadConversations]);

  // ------- Fetch Messages -------
  const loadMessages = useCallback(async (convId: string) => {
    setLoadingMessages(true);
    try {
      const res = await fetch(
        `/api/portal/marketing/conversations/${convId}/messages?limit=50`
      );
      if (res.ok) {
        const body = await res.json();
        setMessages(body.data ?? []);
      }
    } catch {
      // silently fail
    } finally {
      setLoadingMessages(false);
    }
  }, []);

  // ------- Select a Conversation -------
  function handleSelect(id: string) {
    setSelectedId(id);
    setAiSuggestion(null);
    setMobileShowThread(true);
    loadMessages(id);
  }

  // ------- Auto-refresh messages every 10s -------
  useEffect(() => {
    if (refreshIntervalRef.current) {
      clearInterval(refreshIntervalRef.current);
    }

    if (selectedId) {
      refreshIntervalRef.current = setInterval(() => {
        loadMessages(selectedId);
        loadConversations();
      }, 10000);
    }

    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [selectedId, loadMessages, loadConversations]);

  // ------- Send Message -------
  async function handleSend(content: string) {
    if (!selectedId) return;

    // Optimistic local append
    const optimisticMsg: Message = {
      id: `temp-${Date.now()}`,
      direction: "outbound",
      content,
      content_type: "text",
      ai_generated: null,
      human_override: null,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, optimisticMsg]);
    setAiSuggestion(null);

    try {
      const res = await fetch(
        `/api/portal/marketing/conversations/${selectedId}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        }
      );

      if (res.ok) {
        // Replace optimistic with real
        const body = await res.json();
        setMessages((prev) =>
          prev.map((m) => (m.id === optimisticMsg.id ? body.data : m))
        );
        // Refresh conversations list to update preview
        loadConversations();
      } else {
        // Remove optimistic on failure
        setMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
      }
    } catch {
      setMessages((prev) => prev.filter((m) => m.id !== optimisticMsg.id));
    }
  }

  // ------- AI Suggest -------
  async function handleAiSuggest() {
    if (!selectedId || aiLoading) return;
    setAiLoading(true);
    setAiSuggestion(null);

    try {
      const res = await fetch(
        `/api/portal/marketing/conversations/${selectedId}/ai-suggest`,
        { method: "POST" }
      );

      if (res.ok) {
        const body = await res.json();
        setAiSuggestion(body.suggestion ?? null);
      }
    } catch {
      // silently fail
    } finally {
      setAiLoading(false);
    }
  }

  // ------- Mobile Back -------
  function handleBack() {
    setMobileShowThread(false);
    setSelectedId(null);
  }

  // ------- Get selected conversation for header -------
  const selectedConv = conversations.find((c) => c.id === selectedId);

  function getConvDisplayName(conv: Conversation): string {
    if (conv.lead) {
      const parts = [conv.lead.first_name, conv.lead.last_name].filter(Boolean);
      if (parts.length > 0) return parts.join(" ");
      if (conv.lead.email) return conv.lead.email;
    }
    return conv.subject ?? "Unknown Contact";
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        eyebrow="Marketing"
        title="Conversations"
        description={`${conversations.length} conversation${conversations.length !== 1 ? "s" : ""} across every channel.`}
      />

      {/* Split Panel Layout */}
      <div
        className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] overflow-hidden bg-[var(--bg-card)]"
        style={{
          height: "calc(100vh - 260px)",
          minHeight: 500,
        }}
      >
        <div className="flex h-full">
          {/* Left Panel - Conversation List */}
          <div
            className={`w-full md:w-[35%] md:max-w-[400px] flex-shrink-0 border-r border-[rgba(255,255,255,0.06)] flex flex-col ${
              mobileShowThread ? "hidden md:flex" : "flex"
            }`}
          >
            {loadingConversations ? (
              <div className="flex-1 flex items-center justify-center">
                <Loader2 size={24} className="animate-spin text-[#10B981]" />
              </div>
            ) : (
              <ConversationList
                conversations={conversations}
                selectedId={selectedId}
                onSelect={handleSelect}
                channelFilter={channelFilter}
                onChannelFilter={setChannelFilter}
              />
            )}
          </div>

          {/* Right Panel - Message Thread */}
          <div
            className={`flex-1 flex flex-col min-w-0 ${
              mobileShowThread ? "flex" : "hidden md:flex"
            }`}
          >
            {selectedId && selectedConv ? (
              <>
                {/* Thread Header */}
                <div className="flex items-center gap-3 px-4 py-3 border-b border-[rgba(255,255,255,0.06)]">
                  {/* Mobile back button */}
                  <button
                    onClick={handleBack}
                    className="md:hidden p-1 rounded text-[#B0B8C8] hover:text-white transition-colors"
                  >
                    <ArrowLeft size={20} />
                  </button>

                  <div className="min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {getConvDisplayName(selectedConv)}
                    </p>
                    <p className="text-[10px] text-[#6B7280]">
                      {selectedConv.channel.replace(/_/g, " ")} &middot;{" "}
                      {selectedConv.status}
                    </p>
                  </div>
                </div>

                {/* Messages */}
                <MessageThread messages={messages} loading={loadingMessages} />

                {/* Compose */}
                <ComposeBar
                  onSend={handleSend}
                  onAiSuggest={handleAiSuggest}
                  aiSuggestion={aiSuggestion}
                  aiLoading={aiLoading}
                />
              </>
            ) : (
              /* Empty State */
              <div className="flex-1 flex flex-col items-center justify-center px-4">
                <div
                  className="w-16 h-16 rounded-full flex items-center justify-center mb-4"
                  style={{ backgroundColor: "rgba(16,185,129,0.1)" }}
                >
                  <MessageCircle size={28} className="text-[#10B981]" />
                </div>
                <p className="text-sm text-[#B0B8C8] text-center">
                  Select a conversation to view messages
                </p>
                <p className="text-xs text-[#6B7280] mt-1 text-center">
                  Pick a thread from the left panel to get started
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
