"use client";

import { ButtonHTMLAttributes } from "react";
import { Loader2 } from "lucide-react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "danger" | "ghost" | "coral";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

export function Button({
  children,
  variant = "primary",
  size = "md",
  loading = false,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0A0F1C]";

  const variants = {
    primary: "btn-gradient focus:ring-[#6C63FF]",
    secondary:
      "bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] hover:bg-[rgba(255,255,255,0.08)] hover:border-[rgba(108,99,255,0.4)] focus:ring-[#6C63FF]",
    danger:
      "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 focus:ring-red-500",
    ghost:
      "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] focus:ring-[#6C63FF]",
    coral: "btn-coral focus:ring-[#FF6D5A]",
  };

  const sizes = {
    sm: "px-3 py-1.5 text-xs gap-1.5",
    md: "px-4 py-2.5 text-sm gap-2",
    lg: "px-6 py-3 text-base gap-2",
  };

  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <Loader2 className="animate-spin h-4 w-4" />}
      {children}
    </button>
  );
}
