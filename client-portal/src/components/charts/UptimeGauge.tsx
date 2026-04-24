"use client";

import { Card } from "@/components/ui-shadcn/card";
import { useChartTheme } from "@/lib/charts/useChartTheme";

interface UptimeGaugeProps {
  successRate: number;
  totalExecutions: number;
  successful: number;
  failed: number;
}

export function UptimeGauge({
  successRate,
  totalExecutions,
  successful,
  failed,
}: UptimeGaugeProps) {
  const theme = useChartTheme();

  // r=58, circumference = 2π·58 ≈ 364.42
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (successRate / 100) * circumference;

  return (
    <Card variant="default" padding="lg" className="flex flex-col gap-4">
      <h3 className="text-sm font-semibold text-foreground">System Uptime</h3>

      <div className="flex flex-col items-center gap-3">
        <svg
          viewBox="0 0 140 140"
          style={{ width: 140, height: 140 }}
          aria-label={`Uptime: ${successRate}%`}
        >
          <defs>
            <linearGradient id="uptime-grad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%"   stopColor={theme.colors.teal} />
              <stop offset="100%" stopColor={theme.colors.purple} />
            </linearGradient>
          </defs>

          <circle
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke={theme.grid.stroke}
            strokeWidth={10}
            strokeLinecap="round"
          />
          <circle
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke="url(#uptime-grad)"
            strokeWidth={10}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 70 70)"
            style={{ transition: "stroke-dashoffset 1.5s cubic-bezier(0.16, 1, 0.3, 1)" }}
          />

          <text
            x="70" y="66"
            textAnchor="middle"
            fill={theme.text.foreground}
            fontSize="28"
            fontWeight={700}
            fontFamily={theme.axis.fontFamily}
          >
            {successRate}
          </text>
          <text
            x="70" y="84"
            textAnchor="middle"
            fill={theme.text.muted}
            fontSize="12"
            fontWeight={400}
            fontFamily={theme.axis.fontFamily}
          >
            percent
          </text>
        </svg>

        <p className="text-xs text-[var(--text-muted)]">Last 30 days average</p>
      </div>

      <div className="grid grid-cols-3 gap-3 text-center pt-1">
        <Stat label="Total"      value={totalExecutions} labelColor="var(--text-dim)" />
        <Stat label="Successful" value={successful}      labelColor={theme.colors.teal} />
        <Stat label="Failed"     value={failed}          labelColor={theme.colors.danger} />
      </div>
    </Card>
  );
}

function Stat({ label, value, labelColor }: { label: string; value: number; labelColor: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] font-semibold uppercase tracking-wide" style={{ color: labelColor }}>
        {label}
      </span>
      <span className="text-sm font-semibold text-foreground tabular-nums">
        {value.toLocaleString()}
      </span>
    </div>
  );
}
