"use client";

import { HealthGauge } from "./HealthGauge";
import { ComparisonArrow } from "./ComparisonArrow";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { Mail, ClipboardList, Eye } from "lucide-react";

interface ClientHealthData {
  id: string;
  full_name: string;
  company_name: string | null;
  composite_score: number;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
  risk_level: string;
  trend: string;
  days_at_risk: number;
}

interface ClientHealthCardProps {
  client: ClientHealthData;
  onAction: (clientId: string, action: string) => void;
}

function ScoreBar({ label, score }: { label: string; score: number }) {
  const color = score >= 70 ? "#10B981" : score >= 50 ? "#EAB308" : score >= 30 ? "#F97316" : "#EF4444";
  return (
    <div className="flex items-center gap-2">
      <span className="text-[10px] text-[#6B7280] w-16 truncate">{label}</span>
      <div className="flex-1 h-1.5 rounded-full bg-[rgba(255,255,255,0.06)]">
        <div
          className="h-full rounded-full transition-all duration-700"
          style={{ width: `${score}%`, background: color }}
        />
      </div>
      <span className="text-[10px] text-[#B0B8C8] w-6 text-right">{score}</span>
    </div>
  );
}

export function ClientHealthCard({ client, onAction }: ClientHealthCardProps) {
  const initials = client.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const trendValue = client.trend === "improving" ? 5 : client.trend === "declining" ? -5 : 0;

  return (
    <div className="floating-card p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div
          className="w-10 h-10 rounded-xl flex items-center justify-center text-sm font-bold text-white"
          style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)" }}
        >
          {initials}
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-white truncate">{client.full_name}</p>
          {client.company_name && (
            <p className="text-[11px] text-[#6B7280] truncate">{client.company_name}</p>
          )}
        </div>
      </div>

      {/* Gauge + Risk */}
      <div className="flex items-center justify-between">
        <HealthGauge score={client.composite_score} size="sm" />
        <div className="flex flex-col items-end gap-1.5">
          <RiskBadge level={client.risk_level as "low" | "medium" | "high" | "critical"} size="sm" />
          <ComparisonArrow value={trendValue} size="sm" />
          {client.days_at_risk > 0 && (
            <span className="text-[10px] text-[#EF4444]">{client.days_at_risk}d at risk</span>
          )}
        </div>
      </div>

      {/* Score Bars */}
      <div className="space-y-1.5">
        <ScoreBar label="Usage" score={client.usage_score} />
        <ScoreBar label="Payment" score={client.payment_score} />
        <ScoreBar label="Engagement" score={client.engagement_score} />
        <ScoreBar label="Support" score={client.support_score} />
      </div>

      {/* Actions */}
      <div className="flex items-center gap-2 pt-1 border-t border-[rgba(255,255,255,0.06)]">
        <button
          onClick={() => onAction(client.id, "checkin")}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-all"
        >
          <Mail size={12} /> Check-in
        </button>
        <button
          onClick={() => onAction(client.id, "task")}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-all"
        >
          <ClipboardList size={12} /> Task
        </button>
        <button
          onClick={() => onAction(client.id, "view")}
          className="flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-[11px] text-[#10B981] hover:bg-[rgba(16,185,129,0.08)] transition-all"
        >
          <Eye size={12} /> View
        </button>
      </div>
    </div>
  );
}
