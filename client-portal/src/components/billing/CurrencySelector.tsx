"use client";

interface CurrencySelectorProps {
  value: string;
  onChange: (currency: string) => void;
}

const CURRENCIES = [
  { code: "ZAR", label: "ZAR (R)", flag: "ZA" },
  { code: "USD", label: "USD ($)", flag: "US" },
  { code: "EUR", label: "EUR", flag: "EU" },
  { code: "GBP", label: "GBP", flag: "GB" },
];

// Simple flag emoji from country code
function flagEmoji(code: string): string {
  if (code === "EU") return "\uD83C\uDDEA\uD83C\uDDFA";
  const codePoints = [...code.toUpperCase()].map(
    (c) => 0x1f1e6 + c.charCodeAt(0) - 65
  );
  return String.fromCodePoint(...codePoints);
}

export function CurrencySelector({ value, onChange }: CurrencySelectorProps) {
  return (
    <div
      style={{
        display: "inline-flex",
        background: "rgba(255, 255, 255, 0.05)",
        borderRadius: "10px",
        padding: "3px",
        gap: "2px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {CURRENCIES.map((cur) => {
        const isActive = value === cur.code;
        return (
          <button
            key={cur.code}
            onClick={() => onChange(cur.code)}
            style={{
              padding: "6px 14px",
              borderRadius: "8px",
              border: "none",
              fontSize: "13px",
              fontWeight: isActive ? 600 : 400,
              cursor: "pointer",
              background: isActive
                ? "rgba(108, 99, 255, 0.15)"
                : "transparent",
              color: isActive ? "#6C63FF" : "#6B7280",
              transition: "all 0.2s ease",
              fontFamily: "Inter, sans-serif",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
          >
            <span style={{ fontSize: "14px" }}>{flagEmoji(cur.flag)}</span>
            {cur.label}
          </button>
        );
      })}
    </div>
  );
}
