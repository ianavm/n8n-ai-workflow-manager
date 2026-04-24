import { cn } from "@/lib/utils";

export type RiskLevel = "low" | "medium" | "high" | "critical";

interface RiskBadgeProps {
  level: RiskLevel;
  pulse?: boolean;
  size?: "sm" | "md";
  className?: string;
}

const LEVEL: Record<
  RiskLevel,
  {
    label: string;
    color: string;          // text + dot color
    bg: string;             // soft background
    border: string;         // border color
    pulseColor: string;     // pulse aura
  }
> = {
  low: {
    label: "Low Risk",
    color: "var(--health-low)",
    bg: "color-mix(in srgb, var(--health-low) 15%, transparent)",
    border: "color-mix(in srgb, var(--health-low) 30%, transparent)",
    pulseColor: "color-mix(in srgb, var(--health-low) 40%, transparent)",
  },
  medium: {
    label: "Medium",
    color: "var(--health-medium)",
    bg: "color-mix(in srgb, var(--health-medium) 15%, transparent)",
    border: "color-mix(in srgb, var(--health-medium) 30%, transparent)",
    pulseColor: "color-mix(in srgb, var(--health-medium) 40%, transparent)",
  },
  high: {
    label: "High Risk",
    color: "var(--health-high)",
    bg: "color-mix(in srgb, var(--health-high) 15%, transparent)",
    border: "color-mix(in srgb, var(--health-high) 30%, transparent)",
    pulseColor: "color-mix(in srgb, var(--health-high) 40%, transparent)",
  },
  critical: {
    label: "Critical",
    color: "var(--health-critical)",
    bg: "color-mix(in srgb, var(--health-critical) 15%, transparent)",
    border: "color-mix(in srgb, var(--health-critical) 30%, transparent)",
    pulseColor: "color-mix(in srgb, var(--health-critical) 40%, transparent)",
  },
};

export function RiskBadge({ level, pulse, size = "md", className }: RiskBadgeProps) {
  const style = LEVEL[level];
  const shouldPulse = pulse ?? (level === "critical" || level === "high");

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-semibold whitespace-nowrap",
        size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs",
        shouldPulse && "risk-pulse",
        className,
      )}
      style={
        {
          background: style.bg,
          color: style.color,
          borderColor: style.border,
          "--pulse-color": style.pulseColor,
        } as React.CSSProperties
      }
    >
      {shouldPulse ? (
        <span
          aria-hidden
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{ background: style.color }}
        />
      ) : null}
      {style.label}
    </span>
  );
}
