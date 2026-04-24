"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Calendar,
  CheckSquare,
  DollarSign,
  FileText,
  LayoutDashboard,
  Lightbulb,
  MessageCircle,
  type LucideIcon,
  User,
} from "lucide-react";

import { cn } from "@/lib/utils";

interface AdvisoryNavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV: AdvisoryNavItem[] = [
  { label: "Dashboard",      href: "/portal/advisory/dashboard",      icon: LayoutDashboard },
  { label: "Profile",        href: "/portal/advisory/profile",        icon: User },
  { label: "Meetings",       href: "/portal/advisory/meetings",       icon: Calendar },
  { label: "Tasks",          href: "/portal/advisory/tasks",          icon: CheckSquare },
  { label: "Documents",      href: "/portal/advisory/documents",      icon: FileText },
  { label: "Pricing",        href: "/portal/advisory/pricing",        icon: DollarSign },
  { label: "Insights",       href: "/portal/advisory/insights",       icon: Lightbulb },
  { label: "Communications", href: "/portal/advisory/communications", icon: MessageCircle },
];

export default function AdvisoryLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  const isActive = (href: string) =>
    pathname === href ||
    (href !== "/portal/advisory/dashboard" && pathname.startsWith(`${href}/`));

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Advisory sub-navigation */}
      <aside className="lg:w-[220px] lg:shrink-0 lg:sticky lg:top-[calc(var(--topbar-h)+1rem)] lg:self-start">
        <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] backdrop-blur-sm p-2">
          <p className="px-3 pt-2 pb-3 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--accent-teal)]">
            Discovery Advisory
          </p>
          <nav aria-label="Advisory sub-navigation" className="flex flex-col gap-0.5">
            {NAV.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "relative flex items-center gap-2.5 h-9 pl-3 pr-2 text-sm font-medium",
                    "rounded-[var(--radius-sm)] transition-colors duration-[var(--dur-fast)]",
                    active
                      ? "bg-[var(--bg-card-hover)] text-foreground"
                      : "text-[var(--text-muted)] hover:bg-[var(--bg-card-hover)] hover:text-foreground",
                  )}
                >
                  {active ? (
                    <span
                      aria-hidden
                      className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--accent-teal)]"
                    />
                  ) : null}
                  <Icon
                    className={cn(
                      "size-4 shrink-0",
                      active ? "text-[var(--accent-teal)]" : "text-[var(--text-dim)]",
                    )}
                    aria-hidden
                  />
                  <span className="truncate">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Advisory content */}
      <div className="flex-1 min-w-0">{children}</div>
    </div>
  );
}
