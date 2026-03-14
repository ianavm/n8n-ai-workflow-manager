"use client";

interface BadgeProps {
  children: React.ReactNode;
  variant?: "default" | "success" | "warning" | "danger" | "purple" | "coral";
  size?: "sm" | "md";
  pulse?: boolean;
}

const variants = {
  default: "bg-[rgba(255,255,255,0.08)] text-[#B0B8C8] border-[rgba(255,255,255,0.08)]",
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  warning: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  danger: "bg-red-500/10 text-red-400 border-red-500/20",
  purple: "bg-[rgba(108,99,255,0.1)] text-[#6C63FF] border-[rgba(108,99,255,0.2)]",
  coral: "bg-[rgba(255,109,90,0.1)] text-[#FF6D5A] border-[rgba(255,109,90,0.2)]",
};

export function Badge({
  children,
  variant = "default",
  size = "sm",
  pulse = false,
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${variants[variant]} ${
        size === "sm" ? "px-2 py-0.5 text-xs" : "px-3 py-1 text-sm"
      }`}
    >
      {pulse && (
        <span
          className="w-1.5 h-1.5 rounded-full animate-pulse"
          style={{ backgroundColor: "currentColor" }}
        />
      )}
      {children}
    </span>
  );
}
