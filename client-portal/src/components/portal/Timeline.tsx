import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TimelineItemData {
  id: string | number;
  title: ReactNode;
  description?: ReactNode;
  timestamp?: ReactNode;
  /** Accent color for the dot. Defaults to brand primary. */
  accent?: "purple" | "teal" | "coral" | "brand" | "neutral";
  icon?: ReactNode;
}

interface TimelineProps {
  items: TimelineItemData[];
  className?: string;
}

const DOT_COLOR: Record<NonNullable<TimelineItemData["accent"]>, string> = {
  purple: "bg-[var(--accent-purple)]",
  teal:   "bg-[var(--accent-teal)]",
  coral:  "bg-[var(--accent-coral)]",
  brand:  "bg-[var(--brand-primary)]",
  neutral:"bg-[var(--text-dim)]",
};

/**
 * Vertical timeline with gradient line + dots. Used for meeting notes,
 * onboarding steps, activity history.
 */
export function Timeline({ items, className }: TimelineProps) {
  return (
    <ol className={cn("relative pl-7", className)}>
      <span
        aria-hidden
        className="absolute left-[8px] top-1.5 bottom-1.5 w-px bg-gradient-to-b from-[var(--border-accent)] via-[var(--border-subtle)] to-transparent"
      />
      {items.map((item, i) => (
        <li key={item.id} className={cn("relative pb-6", i === items.length - 1 && "pb-0")}>
          <span
            aria-hidden
            className={cn(
              "absolute -left-[7px] top-1.5 size-3.5 rounded-full ring-4 ring-[var(--bg-primary)]",
              DOT_COLOR[item.accent ?? "brand"],
            )}
          />
          <div className="flex flex-col gap-1">
            <div className="flex items-center gap-2 flex-wrap">
              <h4 className="text-sm font-semibold text-foreground">{item.title}</h4>
              {item.timestamp ? (
                <span className="text-xs text-[var(--text-dim)]">{item.timestamp}</span>
              ) : null}
            </div>
            {item.description ? (
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">{item.description}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
