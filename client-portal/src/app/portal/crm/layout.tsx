"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  KanbanSquare,
  LayoutDashboard,
  Mail,
  Settings,
  Upload,
  Users,
  Workflow,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/portal/crm",                label: "Dashboard",      icon: LayoutDashboard, exact: true },
  { href: "/portal/crm/leads",          label: "Leads",          icon: Users },
  { href: "/portal/crm/pipeline",       label: "Pipeline",       icon: KanbanSquare },
  { href: "/portal/crm/communications", label: "Communications", icon: Mail },
  { href: "/portal/crm/agents",         label: "Agents",         icon: Workflow },
  { href: "/portal/crm/imports",        label: "Imports",        icon: Upload },
  { href: "/portal/crm/settings",       label: "Settings",       icon: Settings },
];

export default function CrmLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col gap-6">
      <nav
        aria-label="CRM sub-navigation"
        className="flex items-center gap-1 overflow-x-auto pb-2 scrollbar-hide"
      >
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const isActive = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "inline-flex items-center gap-2 h-9 px-4 whitespace-nowrap rounded-[var(--radius-sm)]",
                "text-sm font-medium transition-colors duration-[var(--dur-fast)]",
                isActive
                  ? "bg-[color-mix(in_srgb,var(--accent-coral)_15%,transparent)] border border-[color-mix(in_srgb,var(--accent-coral)_30%,transparent)] text-[var(--accent-coral)]"
                  : "border border-transparent text-[var(--text-muted)] hover:text-foreground hover:bg-[var(--bg-card-hover)]",
              )}
            >
              <Icon className="size-4" aria-hidden />
              {label}
            </Link>
          );
        })}
      </nav>

      <div
        aria-hidden
        className="h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, color-mix(in srgb, var(--accent-coral) 30%, transparent), transparent)",
        }}
      />

      {children}
    </div>
  );
}
