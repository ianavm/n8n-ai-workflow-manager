"use client";

import { LeadScoreBadge } from "./LeadScoreBadge";

interface LeadCardLead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  source: string;
  score: number | null;
  stage: string;
  created_at: string;
  assigned_agent: string | null;
}

interface LeadCardProps {
  lead: LeadCardLead;
  onDragStart: (e: React.DragEvent<HTMLDivElement>, leadId: string) => void;
}

function getDisplayName(lead: LeadCardLead): string {
  const parts = [lead.first_name, lead.last_name].filter(Boolean);
  if (parts.length > 0) return parts.join(" ");
  return lead.email ?? "Unknown";
}

function getDaysInStage(createdAt: string): number {
  const created = new Date(createdAt);
  const now = new Date();
  const diffMs = now.getTime() - created.getTime();
  return Math.floor(diffMs / (1000 * 60 * 60 * 24));
}

function getInitials(name: string): string {
  return name
    .split(" ")
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

const SOURCE_COLORS: Record<string, string> = {
  website: "#3B82F6",
  google_ads: "#F59E0B",
  meta_ads: "#8B5CF6",
  tiktok_ads: "#EC4899",
  linkedin_ads: "#0EA5E9",
  referral: "#10B981",
  cold_outreach: "#6B7280",
  whatsapp: "#22C55E",
  phone: "#F97316",
  email: "#6366F1",
  event: "#A855F7",
  partner: "#14B8A6",
  organic: "#84CC16",
  other: "#6B7280",
};

export function LeadCard({ lead, onDragStart }: LeadCardProps) {
  const displayName = getDisplayName(lead);
  const daysInStage = getDaysInStage(lead.created_at);
  const sourceColor = SOURCE_COLORS[lead.source] ?? "#6B7280";

  return (
    <div
      draggable="true"
      onDragStart={(e) => onDragStart(e, lead.id)}
      className="p-3 rounded-lg cursor-grab active:cursor-grabbing transition-all hover:bg-[rgba(255,255,255,0.06)]"
      style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.06)",
      }}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <div className="min-w-0">
          <p className="text-sm font-medium text-white truncate">{displayName}</p>
          {lead.email && displayName !== lead.email && (
            <p className="text-xs text-[#6B7280] truncate">{lead.email}</p>
          )}
        </div>
        {lead.score != null && <LeadScoreBadge score={lead.score} />}
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        <span
          className="inline-block px-2 py-0.5 rounded text-[10px] font-medium"
          style={{
            color: sourceColor,
            backgroundColor: `${sourceColor}1A`,
          }}
        >
          {lead.source.replace(/_/g, " ")}
        </span>

        <span className="text-[10px] text-[#6B7280]">
          {daysInStage === 0 ? "today" : `${daysInStage}d`}
        </span>
      </div>

      {lead.assigned_agent && (
        <div className="mt-2 flex items-center gap-1.5">
          <span
            className="w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold text-white"
            style={{ background: "rgba(16,185,129,0.3)" }}
          >
            {getInitials(lead.assigned_agent)}
          </span>
          <span className="text-[10px] text-[#6B7280] truncate">
            {lead.assigned_agent}
          </span>
        </div>
      )}
    </div>
  );
}
