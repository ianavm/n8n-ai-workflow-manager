"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  CalendarDays,
  FileText,
  LayoutDashboard,
  MessageCircle,
  Target,
  Users,
} from "lucide-react";

import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { href: "/portal/marketing",               label: "Dashboard",     icon: LayoutDashboard, exact: true },
  { href: "/portal/marketing/campaigns",     label: "Campaigns",     icon: Target },
  { href: "/portal/marketing/content",       label: "Content",       icon: FileText },
  { href: "/portal/marketing/calendar",      label: "Calendar",      icon: CalendarDays },
  { href: "/portal/marketing/leads",         label: "Leads",         icon: Users },
  { href: "/portal/marketing/conversations", label: "Conversations", icon: MessageCircle },
  { href: "/portal/marketing/reports",       label: "Reports",       icon: BarChart3 },
];

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="flex flex-col gap-6">
      <nav
        aria-label="Marketing sub-navigation"
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
                  ? "bg-[color-mix(in_srgb,var(--accent-teal)_15%,transparent)] border border-[color-mix(in_srgb,var(--accent-teal)_30%,transparent)] text-[var(--accent-teal)]"
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
            "linear-gradient(to right, transparent, color-mix(in srgb, var(--accent-teal) 30%, transparent), transparent)",
        }}
      />

      {children}
    </div>
  );
}
