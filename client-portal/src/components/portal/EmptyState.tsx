import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

import { cn } from "@/lib/utils";
import { Card } from "@/components/ui-shadcn/card";

interface EmptyStateProps {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  /** Render inline without the surrounding Card (for use inside tables, etc.). */
  inline?: boolean;
}

export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
  inline = false,
}: EmptyStateProps) {
  const content = (
    <div className={cn("flex flex-col items-center justify-center text-center gap-3 py-12 px-6", className)}>
      <div className="grid size-12 place-items-center rounded-full bg-[var(--bg-card)] border border-[var(--border-subtle)] text-[var(--text-muted)]">
        {icon ?? <Inbox className="size-5" aria-hidden />}
      </div>
      <h3 className="text-base font-semibold text-foreground">{title}</h3>
      {description ? (
        <p className="max-w-sm text-sm text-[var(--text-muted)] leading-relaxed">{description}</p>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );

  if (inline) return content;

  return (
    <Card variant="default" padding="none">
      {content}
    </Card>
  );
}
