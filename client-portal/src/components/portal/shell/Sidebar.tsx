"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronsLeft, Shield } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-shadcn/button";
import { ScrollArea } from "@/components/ui-shadcn/scroll-area";
import { useBrand } from "@/lib/providers/BrandProvider";
import { NAV_GROUPS, findActiveNavItem } from "@/components/portal/shell/nav-config";
import { UserMenu } from "@/components/portal/shell/UserMenu";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  /** For mobile sheet variant — hide the collapse button. */
  hideCollapse?: boolean;
  /** Called when a nav item is clicked (used to close the mobile sheet). */
  onNavigate?: () => void;
  className?: string;
}

export function Sidebar({ collapsed, onToggle, hideCollapse, onNavigate, className }: SidebarProps) {
  const pathname = usePathname();
  const { companyName, logoUrl, isCustomBranded } = useBrand();
  const activeItem = findActiveNavItem(pathname);

  const displayName = isCustomBranded ? companyName.toUpperCase() : "ANYVISION";

  return (
    <aside
      data-collapsed={collapsed ? "true" : undefined}
      className={cn(
        "flex flex-col h-full",
        "bg-[var(--sidebar)] border-r border-[var(--sidebar-border)]",
        "backdrop-blur-xl",
        "transition-[width] duration-[var(--dur-med)] ease-[var(--ease-out)]",
        collapsed ? "w-[var(--sidebar-w-collapsed)]" : "w-[var(--sidebar-w)]",
        className,
      )}
    >
      {/* Brand */}
      <div
        className={cn(
          "flex items-center gap-2.5 h-16 border-b border-[var(--sidebar-border)] shrink-0",
          collapsed ? "px-3 justify-center" : "px-5",
        )}
      >
        {logoUrl && !collapsed ? (
          <Image
            src={logoUrl}
            alt={companyName}
            width={160}
            height={32}
            className="max-h-8 max-w-[160px] object-contain"
            unoptimized
          />
        ) : (
          <>
            <span
              aria-hidden
              className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]"
            >
              <Shield className="size-4 text-white" />
            </span>
            {!collapsed ? (
              <span className="text-sm font-bold tracking-[0.08em] text-foreground truncate">
                {displayName}
              </span>
            ) : null}
          </>
        )}
      </div>

      {/* Nav */}
      <ScrollArea className="flex-1 min-h-0">
        <nav aria-label="Primary" className="flex flex-col gap-4 px-3 py-4">
          {NAV_GROUPS.map((group) => (
            <div key={group.label} className="flex flex-col gap-0.5">
              {!collapsed ? (
                <p className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-dim)]">
                  {group.label}
                </p>
              ) : null}
              <ul className="flex flex-col gap-0.5">
                {group.items.map((item) => {
                  const active = activeItem?.href === item.href;
                  const Icon = item.icon;
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onNavigate}
                        aria-current={active ? "page" : undefined}
                        className={cn(
                          "relative flex items-center gap-3 h-9 text-sm font-medium rounded-[var(--radius-sm)] transition-colors duration-[var(--dur-fast)]",
                          collapsed ? "justify-center px-0 w-9 mx-auto" : "px-3",
                          active
                            ? "bg-[var(--sidebar-accent)] text-foreground"
                            : "text-[var(--text-muted)] hover:bg-[var(--sidebar-accent)] hover:text-foreground",
                        )}
                        title={collapsed ? item.label : undefined}
                      >
                        {active ? (
                          <span
                            aria-hidden
                            className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--brand-primary)]"
                          />
                        ) : null}
                        <Icon
                          className={cn(
                            "size-4 shrink-0 transition-colors",
                            active ? "text-[var(--brand-primary)]" : "text-[var(--text-dim)] group-hover:text-foreground",
                          )}
                          aria-hidden
                        />
                        {!collapsed ? <span className="truncate">{item.label}</span> : null}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </ScrollArea>

      {/* Status + collapse + user */}
      {!collapsed ? (
        <div className="px-3 pt-2 pb-3 border-t border-[var(--sidebar-border)] flex flex-col gap-2 shrink-0">
          <div className="flex items-center gap-2 px-3 py-2 rounded-[var(--radius-sm)] bg-[var(--sidebar-accent)] text-xs text-[var(--text-muted)]">
            <span className="pulse-dot size-1.5 rounded-full bg-[var(--accent-teal)] shrink-0" aria-hidden />
            All systems operational
          </div>
          <UserMenu variant="sidebar" />
          {!hideCollapse ? (
            <Button
              variant="ghost"
              size="sm"
              onClick={onToggle}
              className="justify-start gap-2 text-[var(--text-dim)] hover:text-foreground h-8"
              aria-label="Collapse sidebar"
            >
              <ChevronsLeft className="size-3.5" />
              <span className="text-xs">Collapse</span>
            </Button>
          ) : null}
        </div>
      ) : !hideCollapse ? (
        <div className="px-2 pt-2 pb-3 border-t border-[var(--sidebar-border)] shrink-0">
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={onToggle}
            aria-label="Expand sidebar"
            className="mx-auto"
          >
            <ChevronsLeft className="size-4 rotate-180" />
          </Button>
        </div>
      ) : null}
    </aside>
  );
}
