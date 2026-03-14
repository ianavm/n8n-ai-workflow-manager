"use client";

interface BillingToggleProps {
  value: "monthly" | "yearly";
  onChange: (value: "monthly" | "yearly") => void;
}

export function BillingToggle({ value, onChange }: BillingToggleProps) {
  return (
    <div
      style={{
        display: "inline-flex",
        alignItems: "center",
        background: "rgba(255, 255, 255, 0.05)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "40px",
        padding: "4px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <button
        onClick={() => onChange("monthly")}
        style={{
          padding: "10px 24px",
          borderRadius: "36px",
          border: "none",
          fontSize: "14px",
          fontWeight: 600,
          cursor: "pointer",
          transition: "all 0.3s ease",
          background:
            value === "monthly" ? "rgba(108, 99, 255, 0.15)" : "transparent",
          color: value === "monthly" ? "#fff" : "#6B7280",
          fontFamily: "Inter, sans-serif",
        }}
      >
        Monthly
      </button>
      <button
        onClick={() => onChange("yearly")}
        style={{
          padding: "10px 24px",
          borderRadius: "36px",
          border: "none",
          fontSize: "14px",
          fontWeight: 600,
          cursor: "pointer",
          transition: "all 0.3s ease",
          background:
            value === "yearly" ? "rgba(108, 99, 255, 0.15)" : "transparent",
          color: value === "yearly" ? "#fff" : "#6B7280",
          display: "flex",
          alignItems: "center",
          gap: "8px",
          fontFamily: "Inter, sans-serif",
        }}
      >
        Annual
        <span
          style={{
            background: "rgba(0, 212, 170, 0.15)",
            color: "#00D4AA",
            fontSize: "11px",
            fontWeight: 700,
            padding: "2px 8px",
            borderRadius: "12px",
          }}
        >
          Save 17%
        </span>
      </button>
    </div>
  );
}
