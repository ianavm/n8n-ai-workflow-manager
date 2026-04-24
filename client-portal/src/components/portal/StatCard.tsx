"use client";

import Link from "next/link";
import type { ComponentProps, ReactNode } from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui-shadcn/card";
import { Skeleton } from "@/components/ui-shadcn/skeleton";
import { AnimatedNumber } from "@/components/dashboard/AnimatedNumber";
import { ComparisonArrow } from "@/components/dashboard/ComparisonArrow";

const accentRing = cva("grid place-items-center rounded-[var(--radius-sm)] size-10 shrink-0", {
  variants: {
    accent: {
      purple: "bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)]",
      teal:   "bg-[color-mix(in_srgb,var(--accent-teal)_12%,transparent)]   text-[var(--accent-teal)]",
      coral:  "bg-[color-mix(in_srgb,var(--accent-coral)_12%,transparent)]  text-[var(--accent-coral)]",
      warning:"bg-[color-mix(in_srgb,var(--warning)_12%,transparent)]        text-[var(--warning)]",
      danger: "bg-[color-mix(in_srgb,var(--danger)_12%,transparent)]         text-[var(--danger)]",
      neutral:"bg-[var(--bg-card-hover)] text-[var(--text-muted)]",
    },
  },
  defaultVariants: { accent: "neutral" },
});

export interface StatCardProps
  extends VariantProps<typeof accentRing> {
  label: ReactNode;
  value: number | string;
  prefix?: string;
  suffix?: string;
  decimals?: number;
  /** Percentage delta. Positive renders green, negative red. */
  delta?: number;
  icon?: ReactNode;
  /** Optional sparkline slot — pass <SparkLine data={…} /> */
  sparkline?: ReactNode;
  /** Slot on the right side of the top row (overrides icon). */
  endSlot?: ReactNode;
  loading?: boolean;
  href?: string;
  /** Render the number in gradient text. */
  gradientNumber?: boolean;
  /** Add a colored accent bar along the card top. */
  cardAccent?: ComponentProps<typeof Card>["accent"];
  className?: string;
}

export function StatCard({
  label,
  value,
  prefix,
  suffix,
  decimals = 0,
  delta,
  icon,
  endSlot,
  sparkline,
  loading = false,
  href,
  gradientNumber = false,
  accent = "neutral",
  cardAccent,
  className,
}: StatCardProps) {
  const content = (
    <Card
      variant={href ? "interactive" : "default"}
      accent={cardAccent}
      padding="md"
      className={cn("flex flex-col gap-4 h-full", className)}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
          {label}
        </p>
        {endSlot ? (
          endSlot
        ) : icon ? (
          <div className={accentRing({ accent })}>{icon}</div>
        ) : null}
      </div>

      <div className="flex items-baseline gap-2 min-h-[40px]">
        {loading ? (
          <Skeleton className="h-8 w-24" />
        ) : typeof value === "number" ? (
          <AnimatedNumber
            value={value}
            prefix={prefix}
            suffix={suffix}
            decimals={decimals}
            className={cn(
              "text-[1.75rem] font-bold leading-none tracking-tight tabular-nums",
              gradientNumber ? "gradient-text-coral" : "text-foreground",
            )}
          />
        ) : (
          <span
            className={cn(
              "text-[1.75rem] font-bold leading-none tracking-tight tabular-nums",
              gradientNumber ? "gradient-text-coral" : "text-foreground",
            )}
          >
            {prefix}
            {value}
            {suffix}
          </span>
        )}
      </div>

      <div className="flex items-center justify-between gap-3 mt-auto">
        {typeof delta === "number" ? (
          <ComparisonArrow value={delta} size="sm" />
        ) : (
          <span className="text-xs text-[var(--text-dim)]">&nbsp;</span>
        )}
        {sparkline ? <div className="flex-1 min-w-0 max-w-[96px]">{sparkline}</div> : null}
      </div>
    </Card>
  );

  if (href) {
    return (
      <Link href={href} className="block h-full">
        {content}
      </Link>
    );
  }

  return content;
}
