"use client";

import { Card as ShadcnCard } from "@/components/ui-shadcn/card";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  variant?: "default" | "gradient" | "floating";
  padding?: "none" | "sm" | "md" | "lg";
}

/**
 * Legacy Card API preserved for admin pages. Renders via the portal-wide
 * shadcn Card primitive with mapped variants so admin inherits the
 * premium tokens without per-page rewrites.
 *
 * Variant map:
 *   default  → shadcn default (glass surface)
 *   gradient → shadcn default + gradient-static accent bar (coral→teal top)
 *   floating → shadcn elevated (heavier shadow)
 */
export function Card({
  children,
  className = "",
  hover,
  variant = "default",
  padding = "md",
}: CardProps) {
  void hover; // legacy prop no-op; hover interactivity handled at the primitive level
  const shadcnVariant = variant === "floating" ? "elevated" : "default";
  const shadcnAccent = variant === "gradient" ? "gradient-static" : "none";

  return (
    <ShadcnCard
      variant={shadcnVariant}
      accent={shadcnAccent}
      padding={padding}
      className={className}
    >
      {children}
    </ShadcnCard>
  );
}
