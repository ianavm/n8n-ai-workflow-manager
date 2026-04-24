"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Activity,
  BarChart3,
  Bot,
  Briefcase,
  Calculator,
  HeadphonesIcon,
  HeartPulse,
  LayoutDashboard,
  LogOut,
  type LucideIcon,
  Megaphone,
  Menu,
  Settings,
  Shield,
  Users,
  X,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-shadcn/button";
import { ScrollArea } from "@/components/ui-shadcn/scroll-area";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard",     href: "/admin",          icon: LayoutDashboard },
      { label: "Activity log",  href: "/admin/activity", icon: Activity },
    ],
  },
  {
    label: "Services",
    items: [
      { label: "Accounting", href: "/admin/accounting", icon: Calculator },
      { label: "Advisory",   href: "/admin/advisory",   icon: Briefcase },
      { label: "Marketing",  href: "/admin/marketing",  icon: Megaphone },
      { label: "AI Agents",  href: "/admin/agents",     icon: Bot },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Clients",       href: "/admin/clients",   icon: Users },
      { label: "Client health", href: "/admin/health",    icon: HeartPulse },
      { label: "Support",       href: "/admin/support",   icon: HeadphonesIcon },
    ],
  },
  {
    label: "Administration",
    items: [
      { label: "Analytics",  href: "/admin/analytics",  icon: BarChart3 },
      { label: "Management", href: "/admin/management", icon: Settings },
    ],
  },
];

const ALL_ITEMS = NAV_GROUPS.flatMap((g) => g.items);

function isItemActive(pathname: string, href: string): boolean {
  if (href === "/admin") return pathname === "/admin";
  if (pathname === href) return true;
  return pathname.startsWith(`${href}/`);
}

function findActive(pathname: string): NavItem | undefined {
  const exact = ALL_ITEMS.find((i) => i.href === pathname);
  if (exact) return exact;
  return ALL_ITEMS.filter((i) => i.href !== "/admin" && pathname.startsWith(`${i.href}/`))
    .sort((a, b) => b.href.length - a.href.length)[0];
}

export function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/admin/login");
  }

  const activeItem = findActive(pathname);

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={cn(
          "admin-sidebar flex-col",
          "bg-[var(--sidebar)] border-r border-[var(--sidebar-border)] backdrop-blur-xl",
        )}
      >
        {/* Brand */}
        <div className="flex items-center gap-2.5 h-16 px-5 border-b border-[var(--sidebar-border)] shrink-0">
          <span
            aria-hidden
            className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]"
          >
            <Shield className="size-4 text-white" />
          </span>
          <span className="text-sm font-bold tracking-[0.08em] text-foreground">
            ANYVISION
          </span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--accent-teal)] ml-auto">
            Admin
          </span>
        </div>

        {/* Nav */}
        <ScrollArea className="flex-1 min-h-0">
          <nav aria-label="Admin navigation" className="flex flex-col gap-4 px-3 py-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="flex flex-col gap-0.5">
                <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-dim)]">
                  {group.label}
                </p>
                <ul className="flex flex-col gap-0.5">
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = activeItem?.href === item.href
                      ? true
                      : isItemActive(pathname, item.href);
                    return (
                      <li key={item.href}>
                        <Link
                          href={item.href}
                          aria-current={active ? "page" : undefined}
                          className={cn(
                            "relative flex items-center gap-3 h-9 px-3 text-sm font-medium",
                            "rounded-[var(--radius-sm)] transition-colors duration-[var(--dur-fast)]",
                            active
                              ? "bg-[var(--sidebar-accent)] text-foreground"
                              : "text-[var(--text-muted)] hover:bg-[var(--sidebar-accent)] hover:text-foreground",
                          )}
                        >
                          {active ? (
                            <span
                              aria-hidden
                              className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--brand-primary)]"
                            />
                          ) : null}
                          <Icon
                            className={cn(
                              "size-4 shrink-0",
                              active ? "text-[var(--brand-primary)]" : "text-[var(--text-dim)]",
                            )}
                            aria-hidden
                          />
                          <span className="truncate">{item.label}</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </ScrollArea>

        {/* Sign out */}
        <div className="px-3 pt-2 pb-4 border-t border-[var(--sidebar-border)] shrink-0">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleLogout}
            className="w-full justify-start gap-2 text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]"
          >
            <LogOut className="size-4" />
            Sign out
          </Button>
        </div>
      </aside>

      {/* Mobile header */}
      <header
        className={cn(
          "lg:hidden fixed top-0 left-0 right-0 h-14 z-40 px-4",
          "flex items-center justify-between",
          "bg-[color-mix(in_srgb,var(--bg-primary)_85%,transparent)] backdrop-blur-xl",
          "border-b border-[var(--border-subtle)]",
        )}
      >
        <div className="flex items-center gap-2">
          <span
            aria-hidden
            className="grid place-items-center size-7 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)]"
          >
            <Shield className="size-3.5 text-white" />
          </span>
          <span className="text-sm font-bold tracking-[0.08em] text-foreground">ANYVISION</span>
          <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--accent-teal)]">
            Admin
          </span>
        </div>
        <Button
          variant="ghost"
          size="icon-sm"
          onClick={() => setMobileOpen((v) => !v)}
          aria-label={mobileOpen ? "Close menu" : "Open menu"}
        >
          {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
        </Button>
      </header>

      {/* Mobile drawer */}
      {mobileOpen ? (
        <div
          className={cn(
            "lg:hidden fixed inset-0 top-14 z-30 px-4 py-4 overflow-y-auto animate-fade-in-up",
            "bg-[var(--sidebar)] backdrop-blur-xl",
          )}
        >
          <nav aria-label="Admin navigation (mobile)" className="flex flex-col gap-4">
            {NAV_GROUPS.map((group) => (
              <div key={group.label} className="flex flex-col gap-0.5">
                <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-dim)]">
                  {group.label}
                </p>
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active = isItemActive(pathname, item.href);
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "flex items-center gap-3 h-10 px-3 rounded-[var(--radius-sm)] text-sm font-medium",
                        active
                          ? "bg-[var(--sidebar-accent)] text-foreground"
                          : "text-[var(--text-muted)]",
                      )}
                    >
                      <Icon className="size-4" />
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            ))}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="w-full justify-start gap-2 mt-2 text-[var(--danger)]"
            >
              <LogOut className="size-4" />
              Sign out
            </Button>
          </nav>
        </div>
      ) : null}
    </>
  );
}
