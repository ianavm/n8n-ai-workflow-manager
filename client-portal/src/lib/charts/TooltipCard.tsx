"use client";

interface TooltipEntry {
  name?: string;
  value?: number | string;
  color?: string;
  dataKey?: string | number;
}

// Recharts passes these via cloneElement — typing them loosely is safer across
// versions than pulling in their generic TooltipProps.
interface TooltipCardProps {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  /** Format numeric values for display — defaults to localized integer. */
  formatValue?: (value: number | string, name?: string) => string;
  /** Override the label formatter (useful for dates). */
  formatLabel?: (label: string) => string;
}

/**
 * Recharts tooltip styled to match the portal Card primitive. Glass
 * surface, multi-series aware, theme-aware (reads CSS vars).
 */
export function TooltipCard({
  active,
  payload,
  label,
  formatValue,
  formatLabel,
}: TooltipCardProps) {
  if (!active || !payload?.length) return null;

  const fmt = formatValue ?? ((v) => (typeof v === "number" ? v.toLocaleString() : String(v)));
  const labelText =
    formatLabel && typeof label === "string"
      ? formatLabel(label)
      : typeof label === "number"
        ? String(label)
        : label;

  return (
    <div
      style={{
        background: "var(--bg-elevated)",
        border: "1px solid var(--border-subtle)",
        borderRadius: "var(--radius-md)",
        padding: "10px 14px",
        backdropFilter: "blur(20px)",
        boxShadow: "0 16px 40px rgba(0,0,0,0.45)",
        fontSize: 12,
        fontFamily: "Inter, sans-serif",
        minWidth: 120,
      }}
    >
      {labelText ? (
        <p style={{ color: "var(--text-dim)", fontSize: 11, marginBottom: 6 }}>{labelText}</p>
      ) : null}
      <ul style={{ display: "flex", flexDirection: "column", gap: 4, margin: 0, padding: 0, listStyle: "none" }}>
        {payload.map((entry, i) => (
          <li
            key={`${entry.dataKey ?? i}`}
            style={{ display: "flex", alignItems: "center", gap: 8, justifyContent: "space-between" }}
          >
            <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
              <span
                style={{
                  display: "inline-block",
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: entry.color,
                }}
              />
              <span style={{ color: "var(--text-muted)" }}>{entry.name ?? entry.dataKey}</span>
            </span>
            <span
              style={{
                color: "var(--text-white)",
                fontWeight: 600,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {entry.value !== undefined ? fmt(entry.value, entry.name) : "—"}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
