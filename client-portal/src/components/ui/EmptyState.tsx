"use client";

import type { ReactNode } from "react";

interface EmptyStateProps {
  icon: ReactNode;
  title: string;
  description: string;
  action?: {
    label: string;
    href: string;
  };
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      <div className="w-14 h-14 rounded-2xl bg-[rgba(108,99,255,0.08)] border border-[rgba(108,99,255,0.15)] flex items-center justify-center text-[#6C63FF] mb-5">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">{title}</h3>
      <p className="text-sm text-[#6B7280] max-w-sm">{description}</p>
      {action && (
        <a
          href={action.href}
          className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
        >
          {action.label}
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="9 18 15 12 9 6" />
          </svg>
        </a>
      )}
    </div>
  );
}
