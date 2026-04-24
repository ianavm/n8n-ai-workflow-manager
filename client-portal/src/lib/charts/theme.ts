/**
 * Chart theme — reads CSS custom properties at runtime so Recharts picks up
 * dark/light mode changes + white-label brand overrides without re-mounting.
 *
 * Always returns concrete hex/rgb strings (Recharts can't consume `var(...)`
 * as a stroke/fill value).
 */

export interface ChartTheme {
  colors: {
    purple:  string;
    teal:    string;
    coral:   string;
    warning: string;
    danger:  string;
    brand:   string;
    /** Recharts series colors, indexed 0–4. */
    series: [string, string, string, string, string];
    /** Health-score thresholds. */
    health: {
      critical: string;
      high:     string;
      medium:   string;
      low:      string;
    };
  };
  surfaces: {
    card:     string;
    elevated: string;
    inset:    string;
  };
  text: {
    foreground: string;
    muted:      string;
    dim:        string;
  };
  grid: {
    stroke:         string;
    strokeDasharray: string;
  };
  axis: {
    stroke:     string;
    fontSize:   number;
    fontFamily: string;
  };
}

const FALLBACK: ChartTheme = {
  colors: {
    purple: "#6C63FF",
    teal:   "#00D4AA",
    coral:  "#FF6D5A",
    warning: "#F59E0B",
    danger:  "#EF4444",
    brand:  "#FF6D5A",
    series: ["#6C63FF", "#00D4AA", "#FF6D5A", "#F59E0B", "#3B82F6"],
    health: { critical: "#EF4444", high: "#F97316", medium: "#EAB308", low: "#00D4AA" },
  },
  surfaces: { card: "#1C1C22", elevated: "#12182A", inset: "rgba(0,0,0,0.2)" },
  text:     { foreground: "#FFFFFF", muted: "#B0B8C8", dim: "#6B7280" },
  grid:     { stroke: "rgba(255,255,255,0.05)", strokeDasharray: "3 3" },
  axis:     { stroke: "#6B7280", fontSize: 12, fontFamily: "Inter, sans-serif" },
};

function readVar(name: string, fallback: string): string {
  if (typeof window === "undefined") return fallback;
  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function getChartTheme(): ChartTheme {
  if (typeof window === "undefined") return FALLBACK;

  const purple  = readVar("--accent-purple", FALLBACK.colors.purple);
  const teal    = readVar("--accent-teal",   FALLBACK.colors.teal);
  const coral   = readVar("--accent-coral",  FALLBACK.colors.coral);
  const warning = readVar("--warning",       FALLBACK.colors.warning);
  const danger  = readVar("--danger",        FALLBACK.colors.danger);
  const brand   = readVar("--brand-primary", FALLBACK.colors.brand);

  return {
    colors: {
      purple,
      teal,
      coral,
      warning,
      danger,
      brand,
      series: [
        readVar("--chart-1", purple),
        readVar("--chart-2", teal),
        readVar("--chart-3", coral),
        readVar("--chart-4", warning),
        readVar("--chart-5", FALLBACK.colors.series[4]),
      ],
      health: {
        critical: readVar("--health-critical", FALLBACK.colors.health.critical),
        high:     readVar("--health-high",     FALLBACK.colors.health.high),
        medium:   readVar("--health-medium",   FALLBACK.colors.health.medium),
        low:      readVar("--health-low",      FALLBACK.colors.health.low),
      },
    },
    surfaces: {
      card:     readVar("--bg-card",     FALLBACK.surfaces.card),
      elevated: readVar("--bg-elevated", FALLBACK.surfaces.elevated),
      inset:    readVar("--bg-inset",    FALLBACK.surfaces.inset),
    },
    text: {
      foreground: readVar("--text-white", FALLBACK.text.foreground),
      muted:      readVar("--text-muted", FALLBACK.text.muted),
      dim:        readVar("--text-dim",   FALLBACK.text.dim),
    },
    grid: {
      stroke:          readVar("--border-subtle", FALLBACK.grid.stroke),
      strokeDasharray: "3 3",
    },
    axis: {
      stroke:     readVar("--text-dim", FALLBACK.axis.stroke),
      fontSize:   12,
      fontFamily: "Inter, sans-serif",
    },
  };
}

/**
 * Pick a health-tier color for a 0–100 score. Uses runtime theme so
 * light/dark swaps are honored.
 */
export function healthColorForScore(score: number, theme: ChartTheme): string {
  if (score < 30) return theme.colors.health.critical;
  if (score < 50) return theme.colors.health.high;
  if (score < 70) return theme.colors.health.medium;
  return theme.colors.health.low;
}
