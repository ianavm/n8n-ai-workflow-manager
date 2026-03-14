"use client";

interface UsageBarProps {
  label: string;
  used: number;
  limit: number;
  unit?: string;
}

export function UsageBar({ label, used, limit, unit }: UsageBarProps) {
  const isUnlimited = limit === -1;
  const percentage = isUnlimited ? 10 : Math.min((used / limit) * 100, 100);

  const fillColor =
    isUnlimited
      ? "#00D4AA"
      : percentage >= 95
        ? "#FF6D5A"
        : percentage >= 80
          ? "#F59E0B"
          : "#6C63FF";

  const formatNumber = (n: number): string =>
    n.toLocaleString("en-ZA");

  const valueText = isUnlimited
    ? `${formatNumber(used)}${unit ? ` ${unit}` : ""} / Unlimited`
    : `${formatNumber(used)} / ${formatNumber(limit)}${unit ? ` ${unit}` : ""}`;

  return (
    <div style={{ marginBottom: "16px", fontFamily: "Inter, sans-serif" }}>
      {/* Label + Value row */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "8px",
        }}
      >
        <span style={{ fontSize: "13px", color: "#B0B8C8" }}>{label}</span>
        <span style={{ fontSize: "13px", color: "#fff", fontWeight: 500 }}>
          {valueText}
        </span>
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: "100%",
          height: "8px",
          borderRadius: "4px",
          background: "rgba(255, 255, 255, 0.05)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${percentage}%`,
            height: "100%",
            borderRadius: "4px",
            background: fillColor,
            transition: "width 0.5s ease, background 0.3s ease",
          }}
        />
      </div>
    </div>
  );
}
