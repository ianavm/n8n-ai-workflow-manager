"use client";

import {
  Badge as ShadcnBadge,
  type BadgeProps as ShadcnBadgeProps,
} from "@/components/ui-shadcn/badge";
import { cn } from "@/lib/utils";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "purple" | "coral";
  size?: "sm" | "md";
  pulse?: boolean;
  className?: string;
}

const TONE_MAP: Record<NonNullable<BadgeProps["variant"]>, ShadcnBadgeProps["tone"]> = {
  default: "neutral",
  success: "success",
  warning: "warning",
  danger:  "danger",
  purple:  "info",
  coral:   "brand",
};

/**
 * Legacy Badge API preserved for admin. Maps old `variant` onto the new
 * badge's `tone` so admin inherits the premium soft-pill treatment.
 */
export function Badge({
  children,
  variant = "default",
  size = "sm",
  pulse = false,
  className,
}: BadgeProps) {
  return (
    <ShadcnBadge
      tone={TONE_MAP[variant]}
      appearance="soft"
      size={size}
      className={className}
    >
      {pulse ? (
        <span
          aria-hidden
          className={cn("inline-block size-1.5 rounded-full bg-current animate-pulse")}
        />
      ) : null}
      {children}
    </ShadcnBadge>
  );
}
