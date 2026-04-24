import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "flex h-10 w-full min-w-0 px-4 py-2",
        "rounded-[10px] bg-[var(--input)] text-foreground",
        "border border-[var(--border-subtle)]",
        "text-sm font-medium placeholder:text-[var(--text-dim)]",
        "shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]",
        "transition-[border-color,box-shadow,background] duration-[var(--dur-med)] ease-[var(--ease-out)]",
        "outline-none file:inline-flex file:h-8 file:border-0 file:bg-transparent file:text-sm file:font-medium",
        "selection:bg-[var(--brand-primary)] selection:text-primary-foreground",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-[var(--brand-primary)] focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--brand-primary)_20%,transparent),0_0_20px_var(--brand-glow)] focus-visible:bg-[color-mix(in_srgb,var(--bg-inset)_60%,transparent)]",
        "aria-invalid:border-[var(--danger)] aria-invalid:shadow-[0_0_0_3px_rgba(239,68,68,0.2)]",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
