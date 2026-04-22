import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import { CardShell } from "./CardShell";

interface KPIStatCardProps {
  label: string;
  value: string | number;
  /** Signed delta (percent or absolute). Positive → up, negative → down. */
  delta?: number | null;
  deltaSuffix?: string;
  hint?: string;
  tone?: "neutral" | "positive" | "negative";
}

export function KPIStatCard({
  label,
  value,
  delta,
  deltaSuffix = "%",
  hint,
  tone = "neutral",
}: KPIStatCardProps) {
  const deltaIcon =
    delta === null || delta === undefined ? (
      <Minus size={14} />
    ) : delta > 0 ? (
      <ArrowUp size={14} />
    ) : delta < 0 ? (
      <ArrowDown size={14} />
    ) : (
      <Minus size={14} />
    );

  const deltaColor =
    delta === null || delta === undefined
      ? "#71717A"
      : delta > 0
        ? tone === "negative"
          ? "#EF4444"
          : "#10B981"
        : delta < 0
          ? tone === "negative"
            ? "#10B981"
            : "#EF4444"
          : "#71717A";

  return (
    <CardShell padded={false}>
      <div className="px-5 py-4">
        <p className="text-[11px] font-semibold tracking-[0.08em] uppercase text-[#71717A]">
          {label}
        </p>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-[28px] font-semibold tracking-tight text-white">
            {value}
          </span>
          {delta !== undefined && (
            <span
              className="inline-flex items-center gap-1 text-xs font-medium"
              style={{ color: deltaColor }}
            >
              {deltaIcon}
              {delta === null ? "—" : `${Math.abs(delta).toFixed(1)}${deltaSuffix}`}
            </span>
          )}
        </div>
        {hint && <p className="mt-1 text-xs text-[#71717A]">{hint}</p>}
      </div>
    </CardShell>
  );
}
