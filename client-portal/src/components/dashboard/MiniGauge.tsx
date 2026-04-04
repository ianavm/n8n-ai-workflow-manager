interface MiniGaugeProps {
  score: number;
  label: string;
  color?: string;
  size?: number;
}

function getScoreColor(score: number): string {
  if (score < 30) return "#EF4444";
  if (score < 50) return "#F97316";
  if (score < 70) return "#EAB308";
  return "#10B981";
}

export function MiniGauge({
  score,
  label,
  color,
  size = 48,
}: MiniGaugeProps) {
  const strokeWidth = 4;
  const radius = (size - strokeWidth) / 2;
  const center = size / 2;
  const circumference = 2 * Math.PI * radius;
  const resolvedColor = color ?? getScoreColor(score);
  const normalizedScore = Math.min(Math.max(score, 0), 100);
  const offset = circumference - (normalizedScore / 100) * circumference;

  return (
    <div
      style={{
        display: "inline-flex",
        flexDirection: "column",
        alignItems: "center",
        gap: "4px",
      }}
    >
      <div style={{ position: "relative", width: size, height: size }}>
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
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
          {/* Fill arc */}
          <circle
            cx={center}
            cy={center}
            r={radius}
            fill="none"
            stroke={resolvedColor}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{
              transition: "stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
          />
        </svg>
        {/* Center number */}
        <span
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: size < 40 ? "10px" : "13px",
            fontWeight: 700,
            color: "#fff",
          }}
        >
          {normalizedScore}
        </span>
      </div>
      <span
        style={{
          fontSize: "10px",
          color: "#6B7280",
          textAlign: "center",
          lineHeight: 1.2,
          maxWidth: size + 16,
        }}
      >
        {label}
      </span>
    </div>
  );
}
