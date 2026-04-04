"use client";

import {
  MessageCircle,
  Mail,
  Smartphone,
  Instagram,
  Facebook,
} from "lucide-react";

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

interface ConversationListProps {
  conversations: Conversation[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  channelFilter: string | null;
  onChannelFilter: (channel: string | null) => void;
}

const CHANNEL_CONFIG: Record<string, { icon: typeof MessageCircle; label: string; color: string }> = {
  whatsapp: { icon: MessageCircle, label: "WhatsApp", color: "#25D366" },
  email: { icon: Mail, label: "Email", color: "#6366F1" },
  sms: { icon: Smartphone, label: "SMS", color: "#F59E0B" },
  instagram_dm: { icon: Instagram, label: "Instagram", color: "#E1306C" },
  facebook_messenger: { icon: Facebook, label: "Messenger", color: "#0084FF" },
};

function getContactName(conv: Conversation): string {
  if (conv.lead) {
    const parts = [conv.lead.first_name, conv.lead.last_name].filter(Boolean);
    if (parts.length > 0) return parts.join(" ");
    if (conv.lead.email) return conv.lead.email;
  }
  return conv.subject ?? "Unknown Contact";
}

function getRelativeTime(dateStr: string | null): string {
  if (!dateStr) return "";
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "now";
  if (diffMins < 60) return `${diffMins}m`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d`;

  const diffWeeks = Math.floor(diffDays / 7);
  return `${diffWeeks}w`;
}

function truncateText(text: string | null, maxLen: number): string {
  if (!text) return "";
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "...";
}

const CHANNELS = Object.keys(CHANNEL_CONFIG);

export function ConversationList({
  conversations,
  selectedId,
  onSelect,
  channelFilter,
  onChannelFilter,
}: ConversationListProps) {
  return (
    <div className="flex flex-col h-full">
      {/* Channel Filter Pills */}
      <div className="flex items-center gap-1.5 px-3 py-3 overflow-x-auto scrollbar-hide">
        <button
          onClick={() => onChannelFilter(null)}
          className={`px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
            channelFilter === null
              ? "bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.3)]"
              : "text-[#B0B8C8] hover:text-white bg-[rgba(255,255,255,0.05)] border border-transparent"
          }`}
        >
          All
        </button>
        {CHANNELS.map((ch) => {
          const config = CHANNEL_CONFIG[ch];
          const Icon = config.icon;
          const isActive = channelFilter === ch;
          return (
            <button
              key={ch}
              onClick={() => onChannelFilter(isActive ? null : ch)}
              className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "border"
                  : "text-[#B0B8C8] hover:text-white bg-[rgba(255,255,255,0.05)] border border-transparent"
              }`}
              style={
                isActive
                  ? {
                      color: config.color,
                      backgroundColor: `${config.color}1A`,
                      borderColor: `${config.color}40`,
                    }
                  : undefined
              }
            >
              <Icon size={12} />
              {config.label}
            </button>
          );
        })}
      </div>

      <div className="h-px bg-[rgba(255,255,255,0.06)]" />

      {/* Conversation Cards */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
            <MessageCircle size={32} className="text-[#6B7280] mb-3" />
            <p className="text-sm text-[#6B7280]">
              No conversations yet. Conversations will appear when leads reach out.
            </p>
          </div>
        ) : (
          conversations.map((conv) => {
            const isSelected = conv.id === selectedId;
            const channelCfg = CHANNEL_CONFIG[conv.channel] ?? CHANNEL_CONFIG.email;
            const ChannelIcon = channelCfg.icon;

            return (
              <button
                key={conv.id}
                onClick={() => onSelect(conv.id)}
                className={`w-full text-left px-3 py-3 transition-all ${
                  isSelected
                    ? "bg-[rgba(16,185,129,0.08)] border-l-2 border-l-[#10B981]"
                    : "border-l-2 border-l-transparent hover:bg-[rgba(255,255,255,0.03)]"
                }`}
                style={{
                  borderBottom: "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <div className="flex items-start gap-2.5">
                  {/* Channel Icon */}
                  <div
                    className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center mt-0.5"
                    style={{ backgroundColor: `${channelCfg.color}1A` }}
                  >
                    <ChannelIcon size={14} style={{ color: channelCfg.color }} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-medium text-white truncate">
                        {getContactName(conv)}
                      </span>
                      <span className="text-[10px] text-[#6B7280] flex-shrink-0">
                        {getRelativeTime(conv.last_message_at ?? conv.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center justify-between gap-2 mt-0.5">
                      <p className="text-xs text-[#6B7280] truncate">
                        {truncateText(conv.last_message_preview, 60) || "No messages yet"}
                      </p>
                      {conv.unread_count > 0 && (
                        <span
                          className="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold text-white"
                          style={{ backgroundColor: "#10B981" }}
                        >
                          {conv.unread_count > 9 ? "9+" : conv.unread_count}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
}
