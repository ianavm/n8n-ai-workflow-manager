interface RiskBadgeProps {
  level: "low" | "medium" | "high" | "critical";
  pulse?: boolean;
  size?: "sm" | "md";
}

const LEVEL_STYLES: Record<string, { bg: string; text: string; label: string; pulseColor: string }> = {
  low: { bg: "rgba(16,185,129,0.12)", text: "#10B981", label: "Low Risk", pulseColor: "rgba(16,185,129,0.4)" },
  medium: { bg: "rgba(234,179,8,0.12)", text: "#EAB308", label: "Medium", pulseColor: "rgba(234,179,8,0.4)" },
  high: { bg: "rgba(249,115,22,0.12)", text: "#F97316", label: "High Risk", pulseColor: "rgba(249,115,22,0.4)" },
  critical: { bg: "rgba(239,68,68,0.12)", text: "#EF4444", label: "Critical", pulseColor: "rgba(239,68,68,0.4)" },
};

export function RiskBadge({ level, pulse, size = "md" }: RiskBadgeProps) {
  const style = LEVEL_STYLES[level] ?? LEVEL_STYLES.low;
  const shouldPulse = pulse ?? (level === "critical" || level === "high");
  const sizeClasses = size === "sm" ? "px-2 py-0.5 text-[10px]" : "px-3 py-1 text-xs";

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-semibold ${sizeClasses} ${shouldPulse ? "risk-pulse" : ""}`}
      style={{
        background: style.bg,
        color: style.text,
        "--pulse-color": style.pulseColor,
      } as React.CSSProperties}
    >
      {shouldPulse && (
        <span
          className="inline-block w-1.5 h-1.5 rounded-full"
          style={{ background: style.text }}
        />
      )}
      {style.label}
    </span>
  );
}
