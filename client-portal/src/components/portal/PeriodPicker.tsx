"use client";

import { cn } from "@/lib/utils";

export type Period = "7d" | "30d" | "90d" | "ytd" | "all";

interface PeriodPickerProps {
  value: Period;
  onChange: (period: Period) => void;
  options?: Period[];
  className?: string;
  "aria-label"?: string;
}

const LABELS: Record<Period, string> = {
  "7d": "7 days",
  "30d": "30 days",
  "90d": "90 days",
  ytd: "YTD",
  all: "All time",
};

/**
 * Segmented control for selecting a date range.
 * Matches the website's pill-row aesthetic. Stateless — parent owns `value`.
 */
export function PeriodPicker({
  value,
  onChange,
  options = ["7d", "30d", "90d"],
  className,
  "aria-label": ariaLabel = "Time period",
}: PeriodPickerProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex items-center gap-1 p-1",
        "rounded-[var(--radius-md)] bg-[var(--bg-card)] border border-[var(--border-subtle)]",
        "backdrop-blur-sm",
        className,
      )}
    >
      {options.map((opt) => {
        const active = opt === value;
        return (
          <button
            key={opt}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onChange(opt)}
            className={cn(
              "h-7 min-w-[56px] px-3 text-xs font-semibold tracking-wide",
              "rounded-[var(--radius-sm)] transition-all duration-[var(--dur-fast)]",
              "focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)]/40",
              active
                ? "bg-[var(--bg-elevated)] text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.3)]"
                : "text-[var(--text-muted)] hover:text-foreground hover:bg-[var(--bg-card-hover)]",
            )}
          >
            {LABELS[opt]}
          </button>
        );
      })}
    </div>
  );
}
