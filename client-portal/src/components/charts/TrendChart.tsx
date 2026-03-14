"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { useState } from "react";

export type Granularity = "daily" | "weekly" | "monthly";

interface TrendChartProps {
  data: { date: string; value: number }[];
  title: string;
  subtitle?: string;
  color?: "purple" | "teal";
  height?: number;
  showGranularity?: boolean;
  onGranularityChange?: (g: Granularity) => void;
}

const colors = {
  purple: { stroke: "#6C63FF", fill: "rgba(108, 99, 255, 0.15)" },
  teal: { stroke: "#00D4AA", fill: "rgba(0, 212, 170, 0.15)" },
};

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: "8px",
        backdropFilter: "blur(20px)",
        padding: "8px 12px",
        fontSize: "12px",
      }}
    >
      <p style={{ color: "#6B7280" }}>{label}</p>
      <p style={{ color: "#fff", fontWeight: 600 }}>{payload[0].value.toLocaleString()}</p>
    </div>
  );
}

export function TrendChart({
  data,
  title,
  subtitle,
  color = "purple",
  height = 160,
  showGranularity = true,
  onGranularityChange,
}: TrendChartProps) {
  const [granularity, setGranularity] = useState<Granularity>("daily");
  const c = colors[color];

  const granularityOptions: { label: string; value: Granularity }[] = [
    { label: "D", value: "daily" },
    { label: "W", value: "weekly" },
    { label: "M", value: "monthly" },
  ];

  return (
    <div className="glass-card" style={{ padding: "24px" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: subtitle ? "4px" : "20px" }}>
        <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>{title}</div>
        {showGranularity && (
          <div style={{ display: "flex", gap: "4px" }}>
            {granularityOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setGranularity(opt.value);
                  onGranularityChange?.(opt.value);
                }}
                style={{
                  padding: "2px 8px",
                  fontSize: "12px",
                  borderRadius: "6px",
                  border: "none",
                  background: granularity === opt.value ? "rgba(108,99,255,0.15)" : "transparent",
                  color: granularity === opt.value ? "#6C63FF" : "#6B7280",
                  cursor: "pointer",
                  fontFamily: "inherit",
                  transition: "all 0.2s",
                }}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {subtitle && (
        <div style={{ fontSize: "12px", color: "#6B7280", marginBottom: "20px" }}>{subtitle}</div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.stroke} stopOpacity={0.3} />
              <stop offset="100%" stopColor={c.stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.05)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#6B7280", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={c.stroke}
            strokeWidth={2.5}
            fill={`url(#gradient-${color})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
