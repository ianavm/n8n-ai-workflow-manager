import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface KPIGridProps {
  children: ReactNode;
  className?: string;
  /** Max columns on xl screens. Responsive cascade: xl → lg → md → sm → base. */
  cols?: 2 | 3 | 4 | 5 | 6;
}

const colClasses: Record<NonNullable<KPIGridProps["cols"]>, string> = {
  2: "grid-cols-1 sm:grid-cols-2",
  3: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3",
  4: "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
  5: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5",
  6: "grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-6",
};

/**
 * Responsive grid wrapper for StatCard rows. 6→3→2→1 by default.
 */
export function KPIGrid({ children, className, cols = 6 }: KPIGridProps) {
  return (
    <div className={cn("grid gap-4 md:gap-5", colClasses[cols], className)}>{children}</div>
  );
}
