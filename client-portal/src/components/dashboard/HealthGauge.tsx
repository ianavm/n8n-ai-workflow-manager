"use client";

import { motion } from "framer-motion";

import { AnimatedNumber } from "./AnimatedNumber";
import { useChartTheme } from "@/lib/charts/useChartTheme";
import { healthColorForScore, type ChartTheme } from "@/lib/charts/theme";

interface BreakdownScores {
  usage: number;
  payment: number;
  engagement: number;
  support: number;
}

interface HealthGaugeProps {
  score: number;
  size?: "sm" | "md" | "lg";
  label?: string;
  showBreakdown?: boolean;
  breakdownScores?: BreakdownScores;
  animate?: boolean;
}

const SIZE_MAP = { sm: 80, md: 140, lg: 200 } as const;

function BreakdownBar({ label, score, theme }: { label: string; score: number; theme: ChartTheme }) {
  const color = healthColorForScore(score, theme);
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[var(--text-dim)] w-[80px] text-right shrink-0">{label}</span>
      <div className="flex-1 h-1 rounded-full bg-[color-mix(in_srgb,var(--text-white)_6%,transparent)] overflow-hidden">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(score, 100)}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          style={{ height: "100%", borderRadius: 999, background: color }}
        />
      </div>
      <span className="text-xs font-semibold text-[var(--text-muted)] w-7 text-right shrink-0 tabular-nums">
        {score}
      </span>
    </div>
  );
}

export function HealthGauge({
  score,
  size = "md",
  label,
  showBreakdown = false,
  breakdownScores,
  animate: shouldAnimate = true,
}: HealthGaugeProps) {
  const theme = useChartTheme();
  const px = SIZE_MAP[size];
  const strokeWidth = size === "sm" ? 6 : size === "md" ? 10 : 12;
  const radius = (px - strokeWidth) / 2;
  const center = px / 2;
  const color = healthColorForScore(score, theme);
  const normalizedScore = Math.min(Math.max(score, 0), 100) / 100;

  const fontSize = size === "sm" ? 18 : size === "md" ? 28 : 40;
  const labelSize = size === "sm" ? 10 : size === "md" ? 12 : 14;

  return (
    <div className="flex flex-col items-center gap-3">
      <div className="relative" style={{ width: px, height: px }}>
        <svg
          width={px}
          height={px}
          viewBox={`0 0 ${px} ${px}`}
          style={{ transform: "rotate(-90deg)" }}
          aria-label={`Health score: ${score}`}
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
          <motion.circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            initial={shouldAnimate ? { pathLength: 0 } : { pathLength: normalizedScore }}
            animate={{ pathLength: normalizedScore }}
            transition={shouldAnimate ? { duration: 1.2, ease: [0.16, 1, 0.3, 1] } : { duration: 0 }}
          />
        </svg>

        <div
          className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none"
          style={{ fontSize }}
        >
          <AnimatedNumber
            value={score}
            duration={shouldAnimate ? 1.2 : 0}
            decimals={0}
            className="font-bold leading-none text-foreground tabular-nums"
          />
          {label ? (
            <span className="mt-0.5 text-[var(--text-dim)]" style={{ fontSize: labelSize }}>
              {label}
            </span>
          ) : null}
        </div>
      </div>

      {showBreakdown && breakdownScores ? (
        <div className="w-full max-w-[260px] flex flex-col gap-1.5">
          <BreakdownBar label="Usage"      score={breakdownScores.usage}      theme={theme} />
          <BreakdownBar label="Payment"    score={breakdownScores.payment}    theme={theme} />
          <BreakdownBar label="Engagement" score={breakdownScores.engagement} theme={theme} />
          <BreakdownBar label="Support"    score={breakdownScores.support}    theme={theme} />
        </div>
      ) : null}
    </div>
  );
}
