import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

interface CardShellProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  padded?: boolean;
  className?: string;
}

/**
 * CRM-local card shell. Reskinned to use portal tokens so it composes
 * cleanly with the wider design system.
 */
export function CardShell({
  title,
  subtitle,
  action,
  children,
  padded = true,
  className,
}: CardShellProps) {
  return (
    <section
      className={cn(
        "rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)]",
        "shadow-[0_1px_2px_rgba(0,0,0,0.35),0_12px_32px_rgba(0,0,0,0.2)]",
        className,
      )}
    >
      {title || action ? (
        <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3 border-b border-[var(--border-subtle)]">
          <div>
            {title ? (
              <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)]">
                {title}
              </h3>
            ) : null}
            {subtitle ? <p className="mt-1 text-xs text-[var(--text-dim)]">{subtitle}</p> : null}
          </div>
          {action ? <div className="shrink-0">{action}</div> : null}
        </header>
      ) : null}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
