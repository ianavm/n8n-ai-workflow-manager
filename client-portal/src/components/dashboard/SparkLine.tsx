"use client";

import { useId } from "react";

import { useChartTheme } from "@/lib/charts/useChartTheme";

interface SparkLineProps {
  data: number[];
  width?: number;
  height?: number;
  /**
   * Color key from the AVM theme. Defaults to coral (primary CTA color)
   * so sparklines match the primary-button accent on the dashboard.
   * Pass a raw hex/rgb to override.
   */
  color?: "purple" | "teal" | "coral" | "brand" | "warning" | "danger" | string;
  className?: string;
}

const TOKEN_KEYS = new Set(["purple", "teal", "coral", "brand", "warning", "danger"]);

export function SparkLine({
  data,
  width = 80,
  height = 24,
  color = "coral",
  className = "",
}: SparkLineProps) {
  const theme = useChartTheme();
  const rawId = useId();
  const gradientId = `spark-${rawId.replace(/[^a-z0-9]/gi, "")}`;

  const stroke = TOKEN_KEYS.has(color)
    ? theme.colors[color as "purple" | "teal" | "coral" | "brand" | "warning" | "danger"]
    : color;

  if (data.length < 2) {
    return <svg width={width} height={height} className={className} aria-hidden />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const padding = range * 0.1;
  const adjustedMin = min - padding;
  const adjustedRange = range + padding * 2;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = height - ((value - adjustedMin) / adjustedRange) * height;
    return `${x},${y}`;
  });

  const polylinePoints = points.join(" ");
  const fillPoints = `${polylinePoints} ${width},${height} 0,${height}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className={className}
      style={{ display: "inline-block", verticalAlign: "middle" }}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"  stopColor={stroke} stopOpacity={0.3} />
          <stop offset="100%" stopColor={stroke} stopOpacity={0} />
        </linearGradient>
      </defs>
      <polygon points={fillPoints} fill={`url(#${gradientId})`} />
      <polyline
        points={polylinePoints}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
