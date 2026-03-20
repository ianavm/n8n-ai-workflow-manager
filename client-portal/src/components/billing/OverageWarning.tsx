"use client";

import { AlertTriangle, ArrowUpRight } from "lucide-react";

interface OverageWarningProps {
  feature: string;
  used: number;
  limit: number;
  overageCount: number;
  level: "warning" | "critical" | "blocked";
  onUpgrade?: () => void;
}

function formatFeatureName(feature: string): string {
  const names: Record<string, string> = {
    messages: "Messages",
    leads: "Leads",
    workflows: "Workflows",
    agents: "AI Agents",
    departments: "Departments",
  };
  return names[feature] || feature;
}

export function OverageWarning({
  feature,
  used,
  limit,
  overageCount,
  level,
  onUpgrade,
}: OverageWarningProps) {
  const config = {
    warning: {
      bg: "rgba(255, 200, 0, 0.08)",
      border: "rgba(255, 200, 0, 0.3)",
      iconColor: "#FFC800",
      title: `${formatFeatureName(feature)} usage at ${Math.round((used / limit) * 100)}%`,
      message: `You've used ${used.toLocaleString()} of ${limit.toLocaleString()} ${formatFeatureName(feature).toLowerCase()}. Consider upgrading to avoid overage charges.`,
    },
    critical: {
      bg: "rgba(255, 109, 90, 0.08)",
      border: "rgba(255, 109, 90, 0.3)",
      iconColor: "#FF6D5A",
      title: `${formatFeatureName(feature)} limit exceeded`,
      message: `You're ${overageCount.toLocaleString()} over your plan limit. Overage charges will apply at the end of your billing period.`,
    },
    blocked: {
      bg: "rgba(255, 50, 50, 0.08)",
      border: "rgba(255, 50, 50, 0.4)",
      iconColor: "#FF3232",
      title: `${formatFeatureName(feature)} hard limit reached`,
      message: `You've reached the maximum overage allowance (2x plan limit). Upgrade your plan to continue.`,
    },
  };

  const c = config[level];

  return (
    <div
      style={{
        background: c.bg,
        border: `1px solid ${c.border}`,
        borderRadius: "12px",
        padding: "16px 20px",
        display: "flex",
        alignItems: "flex-start",
        gap: "14px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <AlertTriangle
        size={20}
        style={{ color: c.iconColor, flexShrink: 0, marginTop: "1px" }}
      />

      <div style={{ flex: 1 }}>
        <p
          style={{
            fontSize: "14px",
            fontWeight: 600,
            color: "#fff",
            margin: "0 0 4px 0",
          }}
        >
          {c.title}
        </p>
        <p
          style={{
            fontSize: "13px",
            color: "#B0B8C8",
            margin: 0,
            lineHeight: 1.5,
          }}
        >
          {c.message}
        </p>
      </div>

      {onUpgrade && (
        <button
          onClick={onUpgrade}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
            color: "#fff",
            border: "none",
            borderRadius: "8px",
            padding: "8px 16px",
            fontSize: "13px",
            fontWeight: 600,
            cursor: "pointer",
            whiteSpace: "nowrap",
            fontFamily: "Inter, sans-serif",
          }}
        >
          Upgrade
          <ArrowUpRight size={14} />
        </button>
      )}
    </div>
  );
}
