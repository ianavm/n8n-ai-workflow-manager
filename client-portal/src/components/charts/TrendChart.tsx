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

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui-shadcn/card";
import { GradientDefs } from "@/lib/charts/GradientDefs";
import { TooltipCard } from "@/lib/charts/TooltipCard";
import { useChartTheme } from "@/lib/charts/useChartTheme";

export type Granularity = "daily" | "weekly" | "monthly";

type SeriesColor = "purple" | "teal" | "coral" | "brand";

interface TrendChartProps {
  data: { date: string; value: number }[];
  title: string;
  subtitle?: string;
  color?: SeriesColor;
  height?: number;
  showGranularity?: boolean;
  onGranularityChange?: (g: Granularity) => void;
  className?: string;
}

const GRANULARITY_OPTIONS: { label: string; value: Granularity }[] = [
  { label: "D", value: "daily" },
  { label: "W", value: "weekly" },
  { label: "M", value: "monthly" },
];

export function TrendChart({
  data,
  title,
  subtitle,
  color = "purple",
  height = 160,
  showGranularity = true,
  onGranularityChange,
  className,
}: TrendChartProps) {
  const theme = useChartTheme();
  const [granularity, setGranularity] = useState<Granularity>("daily");

  const stroke = theme.colors[color];
  const fillId = `avm-fill-${color}`;

  return (
    <Card variant="default" padding="lg" className={cn("flex flex-col gap-2", className)}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        {showGranularity ? (
          <div
            role="tablist"
            aria-label="Chart granularity"
            className="inline-flex items-center gap-0.5 p-0.5 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)]"
          >
            {GRANULARITY_OPTIONS.map((opt) => {
              const active = granularity === opt.value;
              return (
                <button
                  key={opt.value}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  onClick={() => {
                    setGranularity(opt.value);
                    onGranularityChange?.(opt.value);
                  }}
                  className={cn(
                    "h-6 min-w-[24px] px-2 text-[11px] font-semibold uppercase tracking-wide",
                    "rounded-[6px] transition-colors duration-[var(--dur-fast)]",
                    active
                      ? "bg-[var(--bg-elevated)] text-foreground"
                      : "text-[var(--text-dim)] hover:text-foreground hover:bg-[var(--bg-card-hover)]",
                  )}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        ) : null}
      </div>
      {subtitle ? (
        <p className="text-xs text-[var(--text-dim)]">{subtitle}</p>
      ) : null}

      <div className="mt-2">
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
            <GradientDefs />
            <CartesianGrid
              strokeDasharray={theme.grid.strokeDasharray}
              stroke={theme.grid.stroke}
              vertical={false}
            />
            <XAxis
              dataKey="date"
              tick={{ fill: theme.axis.stroke, fontSize: theme.axis.fontSize, fontFamily: theme.axis.fontFamily }}
              axisLine={{ stroke: theme.grid.stroke }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: theme.axis.stroke, fontSize: theme.axis.fontSize, fontFamily: theme.axis.fontFamily }}
              axisLine={false}
              tickLine={false}
              width={36}
            />
            <Tooltip content={<TooltipCard />} cursor={{ stroke: theme.colors.brand, strokeWidth: 1, strokeDasharray: "3 3" }} />
            <Area
              type="monotone"
              dataKey="value"
              stroke={stroke}
              strokeWidth={2}
              fill={`url(#${fillId})`}
              activeDot={{ r: 4, stroke: theme.surfaces.elevated, strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
