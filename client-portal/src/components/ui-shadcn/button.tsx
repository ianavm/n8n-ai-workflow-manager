import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";
import { Loader2 } from "lucide-react";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  [
    "relative inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap",
    "rounded-[var(--radius-md)] text-sm font-semibold",
    "transition-[transform,box-shadow,background,color,border-color] duration-300 ease-[var(--ease-out)]",
    "outline-none focus-visible:ring-[3px] focus-visible:ring-[var(--ring)]/40",
    "disabled:pointer-events-none disabled:opacity-50",
    "[&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  ].join(" "),
  {
    variants: {
      variant: {
        // Primary CTA — coral gradient, glow on hover (matches website .btn-primary)
        default: [
          "text-white border-0",
          "bg-[image:var(--brand-gradient)] bg-[color:var(--brand-primary)]",
          "shadow-[0_1px_0_rgba(255,255,255,0.08)_inset,0_1px_2px_rgba(0,0,0,0.2)]",
          "hover:-translate-y-0.5 hover:shadow-[0_0_30px_var(--brand-glow),0_0_60px_color-mix(in_srgb,var(--brand-primary)_20%,transparent)]",
          "active:translate-y-0",
        ].join(" "),
        // Secondary — transparent with purple border (matches website .btn-secondary)
        secondary: [
          "bg-transparent text-foreground",
          "border border-[var(--border-accent)]",
          "hover:bg-[color-mix(in_srgb,var(--accent-purple)_10%,transparent)]",
          "hover:border-[var(--accent-purple)] hover:-translate-y-0.5",
          "hover:shadow-[0_0_20px_var(--glow-purple)]",
        ].join(" "),
        outline: [
          "bg-transparent text-foreground border border-border",
          "hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-accent)]",
        ].join(" "),
        ghost: [
          "bg-transparent text-[var(--text-muted)]",
          "hover:bg-[var(--bg-card)] hover:text-foreground",
        ].join(" "),
        destructive: [
          "bg-[var(--danger)] text-white",
          "hover:bg-[var(--danger)]/90 hover:shadow-[0_0_20px_rgba(239,68,68,0.3)]",
          "focus-visible:ring-[rgba(239,68,68,0.4)]",
        ].join(" "),
        link: [
          "bg-transparent text-[var(--brand-primary)] underline-offset-4",
          "hover:underline hover:text-[var(--accent-coral-soft)]",
          "px-0 h-auto",
        ].join(" "),
        // Heavy glow variant for marquee moments (upgrade / book / hero CTA)
        glow: [
          "text-white border-0",
          "bg-[image:var(--brand-gradient)] bg-[color:var(--brand-primary)]",
          "shadow-[0_0_24px_var(--brand-glow)]",
          "hover:-translate-y-0.5 hover:shadow-[0_0_40px_var(--brand-glow),0_0_80px_color-mix(in_srgb,var(--brand-primary)_25%,transparent)]",
        ].join(" "),
      },
      size: {
        sm:  "h-8  px-3  text-xs gap-1.5",
        md:  "h-10 px-5  text-sm gap-2",
        lg:  "h-12 px-8  text-base gap-2.5",
        "icon-sm": "size-8  p-0",
        "icon-md": "size-10 p-0",
        "icon-lg": "size-12 p-0",
        // shadcn registry-generated code uses "default" and "icon" — keep aliases for compatibility.
        default: "h-10 px-5 text-sm gap-2",
        icon:    "size-10 p-0",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "md",
    },
  },
);

export interface ButtonProps
  extends React.ComponentProps<"button">,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
}

function Button({
  className,
  variant,
  size,
  asChild = false,
  loading = false,
  disabled,
  children,
  ...props
}: ButtonProps) {
  // `asChild` uses Slot which requires a single React element child — pass
  // the child straight through. `loading` is incompatible with `asChild`.
  if (asChild) {
    return (
      <Slot.Root
        data-slot="button"
        data-variant={variant}
        data-size={size}
        className={cn(buttonVariants({ variant, size, className }))}
        {...props}
      >
        {children}
      </Slot.Root>
    );
  }

  return (
    <button
      data-slot="button"
      data-variant={variant}
      data-size={size}
      data-loading={loading ? "true" : undefined}
      className={cn(buttonVariants({ variant, size, className }))}
      disabled={disabled || loading}
      {...props}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : null}
      {children}
    </button>
  );
}

export { Button, buttonVariants };
