"use client";

import { TrendingUp, TrendingDown } from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: React.ReactNode;
  color?: "purple" | "teal" | "red" | "amber" | "coral";
  loading?: boolean;
}

const iconColors: Record<string, string> = {
  purple: "#6C63FF",
  teal: "#00D4AA",
  red: "#EF4444",
  amber: "#F59E0B",
  coral: "#FF6D5A",
};

const iconBgs: Record<string, string> = {
  purple: "rgba(108,99,255,0.1)",
  teal: "rgba(0,212,170,0.1)",
  red: "rgba(239,68,68,0.1)",
  amber: "rgba(245,158,11,0.1)",
  coral: "rgba(255,109,90,0.1)",
};

export function StatCard({
  title,
  value,
  change,
  icon,
  color = "purple",
  loading = false,
}: StatCardProps) {
  if (loading) {
    return (
      <div className="floating-card" style={{ padding: "24px" }}>
        <Skeleton className="w-12 h-12 mb-4" />
        <Skeleton className="h-8 w-24 mb-2" />
        <Skeleton className="h-4 w-20" />
      </div>
    );
  }

  return (
    <div className="floating-card" style={{ padding: "24px" }}>
      {/* Icon wrap -- 48px, 12px border-radius */}
      <div
        style={{
          width: "48px",
          height: "48px",
          borderRadius: "12px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          marginBottom: "16px",
          backgroundColor: iconBgs[color],
          color: iconColors[color],
        }}
      >
        {icon}
      </div>

      {/* Stat number -- 32px, shimmer gradient text */}
      <div
        className="stat-number-shimmer"
        style={{ marginBottom: "6px" }}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>

      {/* Label -- 13px, muted */}
      <div style={{ fontSize: "13px", color: "#B0B8C8", fontWeight: 400 }}>
        {title}
      </div>

      {/* Percentage badge */}
      {change !== undefined && (
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "4px",
            marginTop: "10px",
            padding: "3px 10px",
            borderRadius: "20px",
            fontSize: "12px",
            fontWeight: 600,
            background: change >= 0 ? "rgba(16,185,129,0.12)" : "rgba(239,68,68,0.12)",
            color: change >= 0 ? "#10B981" : "#EF4444",
          }}
        >
          {change >= 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
          {change >= 0 ? "+" : ""}{change}%
        </span>
      )}
    </div>
  );
}
