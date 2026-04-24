"use client";

import type { ButtonHTMLAttributes } from "react";

import {
  Button as ShadcnButton,
  type ButtonProps as ShadcnButtonProps,
} from "@/components/ui-shadcn/button";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "coral";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const VARIANT_MAP: Record<NonNullable<ButtonProps["variant"]>, ShadcnButtonProps["variant"]> = {
  primary:   "default",      // coral gradient (brand-primary)
  secondary: "secondary",    // transparent w/ purple border
  danger:    "destructive",
  ghost:     "ghost",
  coral:     "default",      // legacy alias — same as primary
};

const SIZE_MAP: Record<NonNullable<ButtonProps["size"]>, ShadcnButtonProps["size"]> = {
  sm: "sm",
  md: "md",
  lg: "lg",
};

/**
 * Legacy Button API preserved for admin pages. Maps old variants
 * (primary/secondary/danger/ghost/coral) onto the new CVA button so admin
 * inherits coral gradients, glow on hover, and modern state styling.
 */
export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <ShadcnButton
      variant={VARIANT_MAP[variant]}
      size={SIZE_MAP[size]}
      loading={loading}
      disabled={disabled}
      {...props}
    >
      {children}
    </ShadcnButton>
  );
}
