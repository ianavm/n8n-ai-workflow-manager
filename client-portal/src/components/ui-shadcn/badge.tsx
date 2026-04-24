import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  [
    "inline-flex w-fit shrink-0 items-center justify-center gap-1 whitespace-nowrap",
    "rounded-full border overflow-hidden font-semibold",
    "transition-colors duration-[var(--dur-fast)]",
    "focus-visible:outline-none focus-visible:ring-[3px]",
    "[&>svg]:pointer-events-none [&>svg]:shrink-0 [&>svg]:size-3",
  ].join(" "),
  {
    variants: {
      tone: {
        neutral: "",
        success: "",
        warning: "",
        danger:  "",
        info:    "",
        brand:   "",
      },
      appearance: {
        soft:    "",
        solid:   "",
        outline: "bg-transparent",
      },
      size: {
        sm: "px-2   py-0.5 text-[11px]",
        md: "px-2.5 py-1   text-xs",
      },
    },
    compoundVariants: [
      // SOFT — tinted background + colored text (default)
      { tone: "neutral", appearance: "soft", className: "bg-[color-mix(in_srgb,var(--text-white)_6%,transparent)] text-[var(--text-muted)] border-[var(--border-subtle)]" },
      { tone: "success", appearance: "soft", className: "bg-[color-mix(in_srgb,var(--accent-teal)_15%,transparent)]   text-[var(--accent-teal)]   border-[color-mix(in_srgb,var(--accent-teal)_30%,transparent)]" },
      { tone: "warning", appearance: "soft", className: "bg-[color-mix(in_srgb,var(--accent-coral)_15%,transparent)]  text-[var(--accent-coral)]  border-[color-mix(in_srgb,var(--accent-coral)_30%,transparent)]" },
      { tone: "danger",  appearance: "soft", className: "bg-[color-mix(in_srgb,var(--danger)_15%,transparent)]         text-[var(--danger)]         border-[color-mix(in_srgb,var(--danger)_30%,transparent)]" },
      { tone: "info",    appearance: "soft", className: "bg-[color-mix(in_srgb,var(--accent-purple)_15%,transparent)]  text-[var(--accent-purple)]  border-[color-mix(in_srgb,var(--accent-purple)_30%,transparent)]" },
      { tone: "brand",   appearance: "soft", className: "bg-[color-mix(in_srgb,var(--brand-primary)_15%,transparent)]  text-[var(--brand-primary)]  border-[color-mix(in_srgb,var(--brand-primary)_30%,transparent)]" },

      // SOLID — filled background, white text
      { tone: "neutral", appearance: "solid", className: "bg-[var(--bg-card-hover)] text-foreground border-transparent" },
      { tone: "success", appearance: "solid", className: "bg-[var(--accent-teal)]   text-white border-transparent" },
      { tone: "warning", appearance: "solid", className: "bg-[var(--accent-coral)]  text-white border-transparent" },
      { tone: "danger",  appearance: "solid", className: "bg-[var(--danger)]        text-white border-transparent" },
      { tone: "info",    appearance: "solid", className: "bg-[var(--accent-purple)] text-white border-transparent" },
      { tone: "brand",   appearance: "solid", className: "bg-[var(--brand-primary)] text-white border-transparent" },

      // OUTLINE — border-only, colored text
      { tone: "neutral", appearance: "outline", className: "border-[var(--border-subtle)] text-[var(--text-muted)]" },
      { tone: "success", appearance: "outline", className: "border-[var(--accent-teal)]   text-[var(--accent-teal)]" },
      { tone: "warning", appearance: "outline", className: "border-[var(--accent-coral)]  text-[var(--accent-coral)]" },
      { tone: "danger",  appearance: "outline", className: "border-[var(--danger)]         text-[var(--danger)]" },
      { tone: "info",    appearance: "outline", className: "border-[var(--accent-purple)]  text-[var(--accent-purple)]" },
      { tone: "brand",   appearance: "outline", className: "border-[var(--brand-primary)]  text-[var(--brand-primary)]" },
    ],
    defaultVariants: {
      tone: "neutral",
      appearance: "soft",
      size: "md",
    },
  },
);

export type BadgeProps = Omit<React.ComponentProps<"span">, "style"> &
  VariantProps<typeof badgeVariants> & {
    asChild?: boolean;
    /** Inline style (kept as standard HTML attribute — use `appearance` for badge visual variant). */
    style?: React.CSSProperties;
  };

function Badge({
  className,
  tone,
  appearance,
  size,
  asChild = false,
  ...props
}: BadgeProps) {
  const Comp = asChild ? Slot.Root : "span";

  return (
    <Comp
      data-slot="badge"
      data-tone={tone}
      data-appearance={appearance}
      className={cn(badgeVariants({ tone, appearance, size }), className)}
      {...props}
    />
  );
}

export { Badge, badgeVariants };
