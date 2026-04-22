import type { ReactNode } from "react";

interface CardShellProps {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  padded?: boolean;
  className?: string;
}

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
      className={`rounded-xl border bg-[#121827] border-[rgba(255,255,255,0.07)] shadow-[0_1px_2px_rgba(0,0,0,0.4),0_12px_32px_rgba(0,0,0,0.25)] ${
        className ?? ""
      }`}
    >
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-4 pb-3 border-b border-[rgba(255,255,255,0.05)]">
          <div>
            {title && (
              <h3 className="text-[13px] font-semibold tracking-wide uppercase text-[#B0B8C8]">
                {title}
              </h3>
            )}
            {subtitle && (
              <p className="mt-1 text-xs text-[#71717A]">{subtitle}</p>
            )}
          </div>
          {action && <div className="flex-shrink-0">{action}</div>}
        </header>
      )}
      <div className={padded ? "p-5" : ""}>{children}</div>
    </section>
  );
}
