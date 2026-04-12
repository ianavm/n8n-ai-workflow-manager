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
  purple: { stroke: "#6366F1", fill: "rgba(99, 102, 241, 0.12)" },
  teal: { stroke: "#10B981", fill: "rgba(16, 185, 129, 0.12)" },
};

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "#1C1C22",
        border: "1px solid rgba(255,255,255,0.08)",
        borderRadius: "6px",
        padding: "8px 12px",
        fontSize: "12px",
      }}
    >
      <p style={{ color: "#71717A" }}>{label}</p>
      <p style={{ color: "#fff", fontWeight: 600, fontVariantNumeric: "tabular-nums" }}>
        {payload[0].value.toLocaleString()}
      </p>
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
      <div className="flex items-center justify-between" style={{ marginBottom: subtitle ? "4px" : "20px" }}>
        <div className="text-sm font-semibold text-white">{title}</div>
        {showGranularity && (
          <div className="flex gap-1">
            {granularityOptions.map((opt) => (
              <button
                key={opt.value}
                onClick={() => {
                  setGranularity(opt.value);
                  onGranularityChange?.(opt.value);
                }}
                className={`px-2 py-0.5 text-xs rounded border-none cursor-pointer font-[inherit] transition-colors duration-150 ${
                  granularity === opt.value
                    ? "bg-[rgba(99,102,241,0.1)] text-[#6366F1]"
                    : "bg-transparent text-[#71717A] hover:text-[#A1A1AA]"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        )}
      </div>
      {subtitle && (
        <div className="text-xs text-[#71717A] mb-5">{subtitle}</div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data} margin={{ top: 5, right: 5, bottom: 5, left: 0 }}>
          <defs>
            <linearGradient id={`gradient-${color}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={c.stroke} stopOpacity={0.2} />
              <stop offset="100%" stopColor={c.stroke} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#71717A", fontSize: 11 }}
            axisLine={{ stroke: "rgba(255,255,255,0.05)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#71717A", fontSize: 11 }}
            axisLine={false}
            tickLine={false}
            width={40}
          />
          <Tooltip content={<CustomTooltip />} />
          <Area
            type="monotone"
            dataKey="value"
            stroke={c.stroke}
            strokeWidth={2}
            fill={`url(#gradient-${color})`}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
