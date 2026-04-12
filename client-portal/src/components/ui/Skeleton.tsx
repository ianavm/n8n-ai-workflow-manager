"use client";

interface SkeletonProps {
  className?: string;
  variant?: "rect" | "circle";
}

export function Skeleton({ className = "", variant = "rect" }: SkeletonProps) {
  return (
    <div
      className={`animate-pulse bg-[rgba(255,255,255,0.06)] ${
        variant === "circle" ? "rounded-full" : "rounded-lg"
      } ${className}`}
      aria-hidden="true"
    />
  );
}

export function StatCardSkeleton() {
  return (
    <div className="glass-card-static p-5 space-y-3">
      <div className="flex items-start justify-between">
        <Skeleton className="w-10 h-10" />
        <Skeleton className="w-14 h-5" />
      </div>
      <Skeleton className="h-8 w-24" />
      <Skeleton className="h-4 w-20" />
    </div>
  );
}

export function TableRowSkeleton({ cols = 6 }: { cols?: number }) {
  return (
    <tr className="border-b border-[rgba(255,255,255,0.04)]">
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className={`h-4 ${i === 0 ? "w-32" : "w-16"}`} />
        </td>
      ))}
    </tr>
  );
}
