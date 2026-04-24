import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex w-full min-h-[120px] resize-vertical px-4 py-3",
        "rounded-[10px] bg-[var(--input)] text-foreground",
        "border border-[var(--border-subtle)]",
        "text-sm font-medium placeholder:text-[var(--text-dim)]",
        "shadow-[inset_0_1px_0_rgba(255,255,255,0.02)]",
        "transition-[border-color,box-shadow,background] duration-[var(--dur-med)] ease-[var(--ease-out)]",
        "outline-none",
        "disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:border-[var(--brand-primary)] focus-visible:shadow-[0_0_0_3px_color-mix(in_srgb,var(--brand-primary)_20%,transparent),0_0_20px_var(--brand-glow)] focus-visible:bg-[color-mix(in_srgb,var(--bg-inset)_60%,transparent)]",
        "aria-invalid:border-[var(--danger)] aria-invalid:shadow-[0_0_0_3px_rgba(239,68,68,0.2)]",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
