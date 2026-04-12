"use client";

import { motion } from "framer-motion";
import { AnimatedNumber } from "./AnimatedNumber";

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

const SIZE_MAP = {
  sm: 80,
  md: 140,
  lg: 200,
} as const;

function getScoreColor(score: number): string {
  if (score < 30) return "#EF4444";
  if (score < 50) return "#F97316";
  if (score < 70) return "#EAB308";
  return "#10B981";
}

function BreakdownBar({
  label,
  score,
}: {
  label: string;
  score: number;
}) {
  const color = getScoreColor(score);

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <span
        style={{
          fontSize: "12px",
          color: "#71717A",
          width: "80px",
          textAlign: "right",
          flexShrink: 0,
        }}
      >
        {label}
      </span>
      <div
        style={{
          flex: 1,
          height: "4px",
          borderRadius: "2px",
          background: "rgba(255,255,255,0.06)",
          overflow: "hidden",
        }}
      >
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.min(score, 100)}%` }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1], delay: 0.3 }}
          style={{
            height: "100%",
            borderRadius: "2px",
            background: color,
          }}
        />
      </div>
      <span
        style={{
          fontSize: "12px",
          color: "#B0B8C8",
          width: "28px",
          textAlign: "right",
          fontWeight: 600,
          flexShrink: 0,
        }}
      >
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
  const px = SIZE_MAP[size];
  const strokeWidth = size === "sm" ? 6 : size === "md" ? 10 : 12;
  const radius = (px - strokeWidth) / 2;
  const center = px / 2;
  const color = getScoreColor(score);
  const normalizedScore = Math.min(Math.max(score, 0), 100) / 100;

  const fontSize = size === "sm" ? 18 : size === "md" ? 28 : 40;
  const labelSize = size === "sm" ? 9 : size === "md" ? 12 : 14;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "12px" }}>
      <svg
        width={px}
        height={px}
        viewBox={`0 0 ${px} ${px}`}
        style={{ transform: "rotate(-90deg)" }}
      >
        {/* Background track */}
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Animated fill */}
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
          transition={
            shouldAnimate
              ? { duration: 1.2, ease: [0.16, 1, 0.3, 1] }
              : { duration: 0 }
          }
          style={{}}
        />
      </svg>

      {/* Center overlay (positioned absolutely over the SVG) */}
      <div
        style={{
          position: "relative",
          marginTop: -px - 12,
          width: px,
          height: px,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          pointerEvents: "none",
        }}
      >
        <AnimatedNumber
          value={score}
          duration={shouldAnimate ? 1.2 : 0}
          className="stat-number-shimmer"
          decimals={0}
        />
        <style>{`
          .health-gauge-score { font-size: ${fontSize}px; font-weight: 700; color: #fff; }
        `}</style>
        <span style={{ fontSize: `${fontSize}px`, fontWeight: 700, color: "#fff", lineHeight: 1 }}>
          {/* AnimatedNumber renders above — this span is a layout helper */}
        </span>
        {label && (
          <span style={{ fontSize: `${labelSize}px`, color: "#71717A", marginTop: "2px" }}>
            {label}
          </span>
        )}
      </div>

      {/* Breakdown bars */}
      {showBreakdown && breakdownScores && (
        <div style={{ width: "100%", maxWidth: "240px", display: "flex", flexDirection: "column", gap: "6px" }}>
          <BreakdownBar label="Usage" score={breakdownScores.usage} />
          <BreakdownBar label="Payment" score={breakdownScores.payment} />
          <BreakdownBar label="Engagement" score={breakdownScores.engagement} />
          <BreakdownBar label="Support" score={breakdownScores.support} />
        </div>
      )}
    </div>
  );
}
