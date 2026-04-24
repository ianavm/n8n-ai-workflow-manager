"use client";

import { useChartTheme } from "@/lib/charts/useChartTheme";
import { healthColorForScore } from "@/lib/charts/theme";

interface MiniGaugeProps {
  score: number;
  label: string;
  /** Override the auto-derived color. Accepts any valid CSS color. */
  color?: string;
  size?: number;
}

export function MiniGauge({ score, label, color, size = 48 }: MiniGaugeProps) {
  const theme = useChartTheme();
  const strokeWidth = 4;
  const radius = (size - strokeWidth) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const resolvedColor = color ?? healthColorForScore(score, theme);
  const normalizedScore = Math.min(Math.max(score, 0), 100);
  const offset = circumference - (normalizedScore / 100) * circumference;

  return (
    <div className="inline-flex flex-col items-center gap-1">
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          style={{ transform: "rotate(-90deg)" }}
        >
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={theme.grid.stroke}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
          />
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={resolvedColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1)" }}
          />
        </svg>
        <span
          className="absolute inset-0 flex items-center justify-center font-bold text-foreground tabular-nums"
          style={{ fontSize: size < 40 ? 10 : 13 }}
        >
          {normalizedScore}
        </span>
      </div>
      <span
        className="text-[10px] text-[var(--text-dim)] text-center leading-tight"
        style={{ maxWidth: size + 16 }}
      >
        {label}
      </span>
    </div>
  );
}
