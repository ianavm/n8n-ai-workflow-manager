import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface BreadcrumbItem {
  label: string;
  href?: string;
}

interface SectionHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  breadcrumb?: BreadcrumbItem[];
  actions?: ReactNode;
  className?: string;
  /** Visual emphasis. `lg` is used for page hero; `md` for section dividers. */
  size?: "md" | "lg";
}

/**
 * Section heading with optional eyebrow, breadcrumb, and actions slot.
 * Matches the website's section label + title + description pattern.
 */
export function SectionHeader({
  title,
  description,
  eyebrow,
  breadcrumb,
  actions,
  size = "md",
  className,
}: SectionHeaderProps) {
  return (
    <header className={cn("flex flex-col gap-3 md:flex-row md:items-end md:justify-between", className)}>
      <div className="flex flex-col gap-2 min-w-0">
        {breadcrumb && breadcrumb.length > 0 ? (
          <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-xs text-[var(--text-dim)]">
            {breadcrumb.map((item, i) => (
              <span key={`${item.label}-${i}`} className="inline-flex items-center gap-1.5">
                {item.href ? (
                  <a
                    href={item.href}
                    className="hover:text-foreground transition-colors"
                  >
                    {item.label}
                  </a>
                ) : (
                  <span className="text-[var(--text-muted)]">{item.label}</span>
                )}
                {i < breadcrumb.length - 1 ? <span aria-hidden className="text-[var(--text-dim)]">/</span> : null}
              </span>
            ))}
          </nav>
        ) : null}

        {eyebrow ? (
          <span className="inline-flex items-center gap-2 text-[0.8rem] font-semibold uppercase tracking-[2px] text-[var(--text-muted)]">
            <span aria-hidden className="h-px w-6 bg-[var(--accent-teal)]" />
            {eyebrow}
          </span>
        ) : null}

        <h1
          className={cn(
            "font-bold text-foreground tracking-[-0.02em] leading-[1.15]",
            size === "lg" ? "text-3xl md:text-[2.5rem]" : "text-2xl",
          )}
        >
          {title}
        </h1>

        {description ? (
          <p className="max-w-2xl text-sm md:text-base text-[var(--text-muted)] leading-relaxed">
            {description}
          </p>
        ) : null}
      </div>

      {actions ? (
        <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div>
      ) : null}
    </header>
  );
}
