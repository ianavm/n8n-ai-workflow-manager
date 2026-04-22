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
    <div className="flex flex-col items-center justify-center text-center py-14 px-6 rounded-xl border border-dashed border-[rgba(255,255,255,0.08)]">
      <div className="w-12 h-12 rounded-full grid place-items-center bg-[rgba(255,109,90,0.1)] border border-[rgba(255,109,90,0.25)]">
        <Icon size={20} color="#FF6D5A" />
      </div>
      <h3 className="mt-4 text-[15px] font-semibold text-white">{title}</h3>
      {description && (
        <p className="mt-1 max-w-md text-sm text-[#B0B8C8]">{description}</p>
      )}
      {(primaryAction || secondaryAction) && (
        <div className="mt-5 flex items-center gap-3">
          {primaryAction}
          {secondaryAction}
        </div>
      )}
    </div>
  );
}
