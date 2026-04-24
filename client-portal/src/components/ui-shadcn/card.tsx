import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const cardVariants = cva(
  [
    "relative overflow-hidden text-card-foreground",
    "rounded-[var(--radius-lg)]",
    "transition-all duration-[var(--dur-slow)] ease-[var(--ease-out)]",
  ].join(" "),
  {
    variants: {
      variant: {
        default:
          "bg-card border border-[var(--border-subtle)]",
        interactive: [
          "bg-card border border-[var(--border-subtle)] cursor-pointer",
          "hover:-translate-y-1 hover:bg-[var(--bg-card-hover)] hover:border-[var(--border-accent)]",
          "hover:shadow-[0_0_30px_var(--glow-purple),0_8px_32px_rgba(0,0,0,0.3)]",
        ].join(" "),
        elevated: [
          "bg-card border border-[var(--border-subtle)]",
          "shadow-[0_4px_24px_rgba(0,0,0,0.25),0_0_0_1px_rgba(255,255,255,0.02)_inset]",
        ].join(" "),
        glass: [
          "bg-[color-mix(in_srgb,var(--bg-card)_70%,transparent)]",
          "backdrop-blur-xl border border-[var(--border-subtle)]",
        ].join(" "),
      },
      accent: {
        none: "",
        purple:
          "before:absolute before:inset-x-0 before:top-0 before:h-[2px] before:bg-[var(--accent-purple)] before:opacity-0 before:transition-opacity before:duration-[var(--dur-med)] hover:before:opacity-100",
        teal:
          "before:absolute before:inset-x-0 before:top-0 before:h-[2px] before:bg-[var(--accent-teal)] before:opacity-0 before:transition-opacity before:duration-[var(--dur-med)] hover:before:opacity-100",
        coral:
          "before:absolute before:inset-x-0 before:top-0 before:h-[2px] before:bg-[var(--accent-coral)] before:opacity-0 before:transition-opacity before:duration-[var(--dur-med)] hover:before:opacity-100",
        gradient:
          "before:absolute before:inset-x-0 before:top-0 before:h-[2px] before:bg-[image:var(--gradient-main)] before:opacity-0 before:transition-opacity before:duration-[var(--dur-med)] hover:before:opacity-100",
        "gradient-static":
          "before:absolute before:inset-x-0 before:top-0 before:h-[3px] before:bg-[image:var(--gradient-main)]",
      },
      padding: {
        none: "",
        sm: "p-4",
        md: "p-6",
        lg: "p-8",
      },
    },
    defaultVariants: {
      variant: "default",
      accent: "none",
      padding: "md",
    },
  },
);

export interface CardProps
  extends React.ComponentProps<"div">,
    VariantProps<typeof cardVariants> {}

function Card({ className, variant, accent, padding, ...props }: CardProps) {
  return (
    <div
      data-slot="card"
      data-variant={variant}
      data-accent={accent}
      className={cn(cardVariants({ variant, accent, padding, className }))}
      {...props}
    />
  );
}

function CardHeader({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-header"
      className={cn(
        "@container/card-header grid auto-rows-min grid-rows-[auto_auto] items-start gap-2 has-data-[slot=card-action]:grid-cols-[1fr_auto] [.border-b]:pb-4 [.border-b]:mb-4",
        className,
      )}
      {...props}
    />
  );
}

function CardTitle({ className, ...props }: React.ComponentProps<"h3">) {
  return (
    <h3
      data-slot="card-title"
      className={cn("text-lg font-semibold leading-none tracking-tight text-foreground", className)}
      {...props}
    />
  );
}

function CardDescription({ className, ...props }: React.ComponentProps<"p">) {
  return (
    <p
      data-slot="card-description"
      className={cn("text-sm text-muted-foreground", className)}
      {...props}
    />
  );
}

function CardAction({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-action"
      className={cn(
        "col-start-2 row-span-2 row-start-1 self-start justify-self-end",
        className,
      )}
      {...props}
    />
  );
}

function CardContent({ className, ...props }: React.ComponentProps<"div">) {
  return <div data-slot="card-content" className={cn("", className)} {...props} />;
}

function CardFooter({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="card-footer"
      className={cn("flex items-center [.border-t]:pt-4 [.border-t]:mt-4", className)}
      {...props}
    />
  );
}

export {
  Card,
  CardHeader,
  CardFooter,
  CardTitle,
  CardAction,
  CardDescription,
  CardContent,
  cardVariants,
};
