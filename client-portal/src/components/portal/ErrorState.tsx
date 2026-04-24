import type { ReactNode } from "react";
import { AlertTriangle, RotateCw } from "lucide-react";

import { Card } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";

interface ErrorStateProps {
  title?: ReactNode;
  description?: ReactNode;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({
  title = "Something went wrong",
  description = "We couldn't load this content. Please try again in a moment.",
  onRetry,
  retryLabel = "Retry",
}: ErrorStateProps) {
  return (
    <Card variant="default" padding="lg">
      <div className="flex flex-col items-center justify-center text-center gap-3 py-6">
        <div className="grid size-12 place-items-center rounded-full bg-[color-mix(in_srgb,var(--danger)_12%,transparent)] text-[var(--danger)]">
          <AlertTriangle className="size-5" aria-hidden />
        </div>
        <h3 className="text-base font-semibold text-foreground">{title}</h3>
        <p className="max-w-sm text-sm text-[var(--text-muted)] leading-relaxed">{description}</p>
        {onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry} className="mt-2">
            <RotateCw className="size-3.5" />
            {retryLabel}
          </Button>
        ) : null}
      </div>
    </Card>
  );
}
