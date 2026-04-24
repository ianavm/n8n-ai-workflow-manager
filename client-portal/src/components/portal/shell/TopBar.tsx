"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Menu } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-shadcn/button";
import { Separator } from "@/components/ui-shadcn/separator";
import { ThemeToggle } from "@/components/portal/shell/ThemeToggle";
import { NotificationsMenu } from "@/components/portal/shell/NotificationsMenu";
import { UserMenu } from "@/components/portal/shell/UserMenu";
import { CommandPaletteTrigger } from "@/components/portal/shell/CommandPalette";
import { buildBreadcrumbs } from "@/components/portal/shell/breadcrumbs";

interface TopBarProps {
  onMobileMenuOpen: () => void;
  onCommandOpen: () => void;
}

export function TopBar({ onMobileMenuOpen, onCommandOpen }: TopBarProps) {
  const pathname = usePathname();
  const trail = buildBreadcrumbs(pathname);

  return (
    <header
      className={cn(
        "sticky top-0 z-40 flex items-center gap-3 px-4 md:px-6 h-[var(--topbar-h)]",
        "bg-[color-mix(in_srgb,var(--bg-primary)_75%,transparent)] backdrop-blur-xl",
        "border-b border-[var(--border-subtle)]",
      )}
    >
      {/* Mobile menu trigger */}
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={onMobileMenuOpen}
        aria-label="Open navigation"
        className="lg:hidden"
      >
        <Menu className="size-4" />
      </Button>

      {/* Breadcrumb */}
      <nav aria-label="Breadcrumb" className="hidden sm:flex items-center gap-1.5 text-sm min-w-0">
        {trail.map((item, i) => (
          <span key={`${item.label}-${i}`} className="flex items-center gap-1.5 min-w-0">
            {i > 0 ? <span aria-hidden className="text-[var(--text-dim)]">/</span> : null}
            {item.href ? (
              <Link
                href={item.href}
                className="text-[var(--text-muted)] hover:text-foreground transition-colors truncate"
              >
                {item.label}
              </Link>
            ) : (
              <span className="font-medium text-foreground truncate">{item.label}</span>
            )}
          </span>
        ))}
      </nav>

      <div className="flex-1" />

      {/* Search / command palette trigger */}
      <CommandPaletteTrigger onOpen={onCommandOpen} />

      <Separator orientation="vertical" className="h-5 hidden md:block" />

      {/* Bell + theme + avatar */}
      <div className="flex items-center gap-1">
        <NotificationsMenu />
        <ThemeToggle />
        <div className="ml-1 hidden md:block">
          <UserMenu variant="topbar" />
        </div>
      </div>
    </header>
  );
}
