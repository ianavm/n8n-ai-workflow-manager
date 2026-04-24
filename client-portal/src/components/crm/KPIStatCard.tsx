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
      <Minus className="size-3.5" />
    ) : delta > 0 ? (
      <ArrowUp className="size-3.5" />
    ) : delta < 0 ? (
      <ArrowDown className="size-3.5" />
    ) : (
      <Minus className="size-3.5" />
    );

  const deltaColor =
    delta === null || delta === undefined
      ? "var(--text-dim)"
      : delta > 0
        ? tone === "negative"
          ? "var(--danger)"
          : "var(--accent-teal)"
        : delta < 0
          ? tone === "negative"
            ? "var(--accent-teal)"
            : "var(--danger)"
          : "var(--text-dim)";

  return (
    <CardShell padded={false}>
      <div className="px-5 py-4">
        <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">
          {label}
        </p>
        <div className="mt-2 flex items-baseline gap-3">
          <span className="text-[28px] font-semibold tracking-tight text-foreground tabular-nums">
            {value}
          </span>
          {delta !== undefined ? (
            <span
              className="inline-flex items-center gap-1 text-xs font-medium"
              style={{ color: deltaColor }}
            >
              {deltaIcon}
              {delta === null ? "—" : `${Math.abs(delta).toFixed(1)}${deltaSuffix}`}
            </span>
          ) : null}
        </div>
        {hint ? <p className="mt-1 text-xs text-[var(--text-dim)]">{hint}</p> : null}
      </div>
    </CardShell>
  );
}
