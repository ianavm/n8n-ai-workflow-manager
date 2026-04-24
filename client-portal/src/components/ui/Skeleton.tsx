"use client";

import { Skeleton as ShadcnSkeleton } from "@/components/ui-shadcn/skeleton";
import { Card } from "@/components/ui-shadcn/card";
import { cn } from "@/lib/utils";

interface SkeletonProps {
  className?: string;
  variant?: "rect" | "circle";
}

/**
 * Legacy skeleton API preserved for admin. Forwards to ui-shadcn Skeleton
 * so admin inherits token-driven rendering.
 */
export function Skeleton({ className = "", variant = "rect" }: SkeletonProps) {
  return (
    <ShadcnSkeleton
      className={cn(
        variant === "circle" ? "rounded-full" : "rounded-[var(--radius-sm)]",
        className,
      )}
      aria-hidden
    />
  );
}

export function StatCardSkeleton() {
  return (
    <Card variant="default" padding="md" className="flex flex-col gap-3">
      <div className="flex items-start justify-between">
        <ShadcnSkeleton className="size-10 rounded-[var(--radius-sm)]" />
        <ShadcnSkeleton className="h-5 w-14" />
      </div>
      <ShadcnSkeleton className="h-8 w-24" />
      <ShadcnSkeleton className="h-4 w-20" />
    </Card>
  );
}

export function TableRowSkeleton({ cols = 6 }: { cols?: number }) {
  return (
    <tr className="border-b border-[var(--border-subtle)]">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <ShadcnSkeleton className={i === 0 ? "h-4 w-32" : "h-4 w-16"} />
        </td>
      ))}
    </tr>
  );
}
