"use client";

interface UptimeGaugeProps {
  successRate: number;
  totalExecutions: number;
  successful: number;
  failed: number;
}

export function UptimeGauge({
  successRate,
  totalExecutions,
  successful,
  failed,
}: UptimeGaugeProps) {
  // Match V1 preview: r=58, circumference = 2*PI*58 = 364.42
  const radius = 58;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (successRate / 100) * circumference;

  return (
    <div className="glass-card" style={{ padding: "24px" }}>
      <h3 style={{ fontSize: "15px", fontWeight: 600, color: "#fff", marginBottom: "16px" }}>
        System Uptime
      </h3>
      <div className="gauge-wrap">
        {/* SVG gauge -- 140px, matching V1 preview exactly */}
        <svg
          className="gauge-svg"
          viewBox="0 0 140 140"
          style={{ width: "140px", height: "140px", marginBottom: "12px" }}
        >
          <defs>
            <linearGradient id="gaugeGrad" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#00D4AA" />
              <stop offset="100%" stopColor="#6C63FF" />
            </linearGradient>
          </defs>
          {/* Background track */}
          <circle
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth="10"
            strokeLinecap="round"
          />
          {/* Active arc */}
          <circle
            cx="70"
            cy="70"
            r={radius}
            fill="none"
            stroke="url(#gaugeGrad)"
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            transform="rotate(-90 70 70)"
            style={{ transition: "stroke-dashoffset 1.5s cubic-bezier(0.16, 1, 0.3, 1)" }}
          />
          {/* Center text */}
          <text
            x="70"
            y="66"
            textAnchor="middle"
            fill="white"
            fontSize="28"
            fontWeight="700"
            fontFamily="Inter, sans-serif"
          >
            {successRate}
          </text>
          <text
            x="70"
            y="84"
            textAnchor="middle"
            fill="#B0B8C8"
            fontSize="12"
            fontWeight="400"
            fontFamily="Inter, sans-serif"
          >
            percent
          </text>
        </svg>
        <div style={{ fontSize: "13px", color: "#B0B8C8" }}>
          Last 30 days average
        </div>
      </div>

      {/* Stats below gauge */}
      <div style={{ display: "flex", justifyContent: "center", gap: "32px", marginTop: "16px", fontSize: "13px" }}>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#6B7280" }}>Total</div>
          <div style={{ color: "#fff", fontWeight: 600 }}>{totalExecutions.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#10B981" }}>Successful</div>
          <div style={{ color: "#fff", fontWeight: 600 }}>{successful.toLocaleString()}</div>
        </div>
        <div style={{ textAlign: "center" }}>
          <div style={{ color: "#EF4444" }}>Failed</div>
          <div style={{ color: "#fff", fontWeight: 600 }}>{failed.toLocaleString()}</div>
        </div>
      </div>
    </div>
  );
}
