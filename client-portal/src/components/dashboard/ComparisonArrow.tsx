import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface ComparisonArrowProps {
  value: number;
  size?: "sm" | "md";
  showValue?: boolean;
}

export function ComparisonArrow({
  value,
  size = "sm",
  showValue = true,
}: ComparisonArrowProps) {
  const isPositive = value > 0;
  const isNegative = value < 0;
  const isZero = value === 0;

  const iconSize = size === "sm" ? 12 : 14;
  const textSize = size === "sm" ? "11px" : "13px";
  const px = size === "sm" ? "6px" : "8px";
  const py = size === "sm" ? "2px" : "3px";

  const config = isPositive
    ? {
        bg: "rgba(16,185,129,0.12)",
        text: "#10B981",
        Icon: TrendingUp,
        prefix: "+",
      }
    : isNegative
      ? {
          bg: "rgba(239,68,68,0.12)",
          text: "#EF4444",
          Icon: TrendingDown,
          prefix: "",
        }
      : {
          bg: "rgba(107,114,128,0.12)",
          text: "#6B7280",
          Icon: Minus,
          prefix: "",
        };

  const formatted = isZero
    ? "0%"
    : `${config.prefix}${Math.abs(value).toFixed(1)}%`;

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
