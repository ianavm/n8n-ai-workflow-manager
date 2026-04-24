import { Card } from "@/components/ui-shadcn/card";
import { Skeleton } from "@/components/ui-shadcn/skeleton";
import { cn } from "@/lib/utils";

interface LoadingStateProps {
  variant?: "card" | "table" | "dashboard" | "list";
  rows?: number;
  className?: string;
}

/**
 * Semantic loading skeleton. Variants model the typical page regions so
 * pages can drop a single <LoadingState> without hand-rolling layouts.
 */
export function LoadingState({ variant = "card", rows = 4, className }: LoadingStateProps) {
  if (variant === "table") {
    return (
      <div className={cn("space-y-3", className)}>
        <Skeleton className="h-10 w-full" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (variant === "list") {
    return (
      <div className={cn("space-y-2", className)}>
        {Array.from({ length: rows }).map((_, i) => (
          <div key={i} className="flex items-center gap-3">
            <Skeleton className="size-10 rounded-full" />
            <div className="flex-1 space-y-1.5">
              <Skeleton className="h-4 w-1/3" />
              <Skeleton className="h-3 w-2/3" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  if (variant === "dashboard") {
    return (
      <div className={cn("space-y-6", className)}>
        <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Card key={i} padding="md">
              <Skeleton className="h-3 w-16 mb-3" />
              <Skeleton className="h-8 w-24 mb-2" />
              <Skeleton className="h-3 w-12" />
            </Card>
          ))}
        </div>
        <Card padding="lg">
          <Skeleton className="h-5 w-40 mb-4" />
          <Skeleton className="h-[240px] w-full" />
        </Card>
      </div>
    );
  }

  // card (default)
  return (
    <Card padding="lg" className={className}>
      <div className="space-y-3">
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} className={i === 0 ? "h-5 w-1/3" : "h-4 w-full"} />
        ))}
      </div>
    </Card>
  );
}
