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
    "inline-flex items-center justify-center font-semibold rounded-lg transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#09090B]";

  const variants = {
    primary: "btn-gradient focus:ring-[#6366F1]",
    secondary:
      "bg-[#1C1C22] border border-[rgba(255,255,255,0.08)] text-[#A1A1AA] hover:bg-[#27272A] hover:border-[rgba(255,255,255,0.12)] focus:ring-[#6366F1]",
    danger:
      "bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 focus:ring-red-500",
    ghost:
      "text-[#A1A1AA] hover:text-white hover:bg-[rgba(255,255,255,0.05)] focus:ring-[#6366F1]",
    coral: "btn-gradient focus:ring-[#6366F1]",
  };

  const sizes = {
    sm: "px-3.5 py-2 text-xs gap-1.5",
    md: "px-5 py-3 text-sm gap-2",
    lg: "px-7 py-3.5 text-base gap-2.5",
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
