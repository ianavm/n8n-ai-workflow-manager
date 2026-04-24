"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";
import { useIdleLogout } from "@/hooks/useIdleLogout";
import { Sidebar } from "@/components/portal/shell/Sidebar";
import { MobileSidebar } from "@/components/portal/shell/MobileSidebar";
import { TopBar } from "@/components/portal/shell/TopBar";
import { CommandPalette } from "@/components/portal/shell/CommandPalette";

const COLLAPSE_KEY = "portal-sidebar-collapsed";

interface PortalShellProps {
  children: ReactNode;
}

function readCollapsedPref(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(COLLAPSE_KEY) === "true";
  } catch {
    return false;
  }
}

export function PortalShell({ children }: PortalShellProps) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);

  // Hydrate collapsed state from localStorage after mount
  useEffect(() => {
    setCollapsed(readCollapsedPref());
  }, []);

  // Login page renders full-bleed without the shell
  const isLogin = pathname === "/portal/login";

  // Auto sign-out after 30min idle (no-op on login page)
  useIdleLogout();

  const toggleCollapse = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_KEY, String(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  // Global ⌘K / Ctrl+K to open the command palette
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setCommandOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Close mobile sheet whenever the route changes
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  if (isLogin) {
    return (
      <>
        {children}
        <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
      </>
    );
  }

  return (
    <div className="relative min-h-screen">
      {/* Desktop sidebar */}
      <div
        className={cn(
          "hidden lg:block fixed inset-y-0 left-0 z-40",
          "transition-[width] duration-[var(--dur-med)] ease-[var(--ease-out)]",
          collapsed ? "w-[var(--sidebar-w-collapsed)]" : "w-[var(--sidebar-w)]",
        )}
      >
        <Sidebar collapsed={collapsed} onToggle={toggleCollapse} />
      </div>

      {/* Mobile sheet */}
      <MobileSidebar open={mobileOpen} onOpenChange={setMobileOpen} />

      {/* Main column */}
      <div
        className={cn(
          "min-h-screen transition-[padding] duration-[var(--dur-med)] ease-[var(--ease-out)]",
          collapsed ? "lg:pl-[var(--sidebar-w-collapsed)]" : "lg:pl-[var(--sidebar-w)]",
        )}
      >
        <TopBar
          onMobileMenuOpen={() => setMobileOpen(true)}
          onCommandOpen={() => setCommandOpen(true)}
        />
        <main className="relative z-[1]">
          <div className="mx-auto max-w-[1400px] px-4 md:px-6 lg:px-8 py-6 md:py-8">
            {children}
          </div>
        </main>
      </div>

      <CommandPalette open={commandOpen} onOpenChange={setCommandOpen} />
    </div>
  );
}
