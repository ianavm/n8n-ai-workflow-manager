import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: string;
  primaryAction?: ReactNode;
  secondaryAction?: ReactNode;
}

export function EmptyState({
  icon: Icon,
  title,
  description,
  primaryAction,
  secondaryAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-14 px-6 rounded-[var(--radius-lg)] border border-dashed border-[var(--border-subtle)] bg-[var(--bg-card)]">
      <div className="size-12 rounded-full grid place-items-center bg-[color-mix(in_srgb,var(--accent-coral)_12%,transparent)] border border-[color-mix(in_srgb,var(--accent-coral)_25%,transparent)]">
        <Icon className="size-5 text-[var(--accent-coral)]" aria-hidden />
      </div>
      <h3 className="mt-4 text-base font-semibold text-foreground">{title}</h3>
      {description ? (
        <p className="mt-1 max-w-md text-sm text-[var(--text-muted)] leading-relaxed">
          {description}
        </p>
      ) : null}
      {primaryAction || secondaryAction ? (
        <div className="mt-5 flex items-center gap-3">
          {primaryAction}
          {secondaryAction}
        </div>
      ) : null}
    </div>
  );
}
