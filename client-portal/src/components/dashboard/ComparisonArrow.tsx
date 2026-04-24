import { Minus, TrendingDown, TrendingUp } from "lucide-react";

interface ComparisonArrowProps {
  /**
   * Signed percentage change. `null` / `undefined` → "no comparison available"
   * (renders a neutral em-dash rather than fabricating "+0%").
   */
  value: number | null | undefined;
  size?: "sm" | "md";
  showValue?: boolean;
  /**
   * Override the renderer's sign direction — useful for metrics where
   * "lower is better" (e.g. overdue invoices, crash count). Default `"higher"`.
   */
  positiveDirection?: "higher" | "lower";
}

export function ComparisonArrow({
  value,
  size = "sm",
  showValue = true,
  positiveDirection = "higher",
}: ComparisonArrowProps) {
  const iconSize = size === "sm" ? 12 : 14;
  const textSize = size === "sm" ? "11px" : "13px";
  const px = size === "sm" ? "6px" : "8px";
  const py = size === "sm" ? "2px" : "3px";

  // No data → neutral em-dash. Don't lie with "+0%".
  if (value === null || value === undefined || Number.isNaN(value)) {
    return (
      <span
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "3px",
          background: "color-mix(in srgb, var(--text-dim) 12%, transparent)",
          color: "var(--text-dim)",
          borderRadius: "9999px",
          padding: `${py} ${px}`,
          fontSize: textSize,
          fontWeight: 600,
          lineHeight: 1,
          whiteSpace: "nowrap",
        }}
        title="No comparison data available"
        aria-label="No comparison data available"
      >
        <Minus size={iconSize} />
        {showValue && <span>—</span>}
      </span>
    );
  }

  const isPositive = value > 0;
  const isNegative = value < 0;
  const isZero = value === 0;

  // Sign → semantic direction. For "lower is better" metrics, positive moves
  // are bad (e.g. +15% overdue invoices).
  const goodMove =
    positiveDirection === "higher"
      ? isPositive
      : positiveDirection === "lower"
        ? isNegative
        : false;
  const badMove =
    positiveDirection === "higher"
      ? isNegative
      : positiveDirection === "lower"
        ? isPositive
        : false;

  const config = isZero
    ? {
        bg: "color-mix(in srgb, var(--text-dim) 12%, transparent)",
        text: "var(--text-dim)",
        Icon: Minus,
      }
    : goodMove
      ? {
          bg: "color-mix(in srgb, var(--accent-teal) 15%, transparent)",
          text: "var(--accent-teal)",
          Icon: isPositive ? TrendingUp : TrendingDown,
        }
      : badMove
        ? {
            bg: "color-mix(in srgb, var(--danger) 15%, transparent)",
            text: "var(--danger)",
            Icon: isPositive ? TrendingUp : TrendingDown,
          }
        : {
            bg: "color-mix(in srgb, var(--text-dim) 12%, transparent)",
            text: "var(--text-dim)",
            Icon: Minus,
          };

  const absolute = Math.abs(value);
  // 1 decimal for sub-100% moves, no decimals above 100% (avoids "+123.0%")
  const formatted = isZero
    ? "0%"
    : `${isPositive ? "+" : "-"}${absolute >= 100 ? Math.round(absolute) : absolute.toFixed(1)}%`;

  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "3px",
        background: config.bg,
        color: config.text,
        borderRadius: "9999px",
        padding: `${py} ${px}`,
        fontSize: textSize,
        fontWeight: 600,
        lineHeight: 1,
        whiteSpace: "nowrap",
      }}
    >
      <config.Icon size={iconSize} />
      {showValue && <span>{formatted}</span>}
    </span>
  );
}
