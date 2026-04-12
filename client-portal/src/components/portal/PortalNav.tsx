"use client";

import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useState, useEffect, useCallback, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import {
  LayoutDashboard,
  Zap,
  Bot,
  FileText,
  CreditCard,
  Settings,
  LogOut,
  Menu,
  X,
  Bell,
  FileBarChart,
  MessageCircle,
  HeadphonesIcon,
  Briefcase,
  Receipt,
  Megaphone,
  HeartPulse,
  Plug,
  Shield,
} from "lucide-react";
import { useTheme } from "@/lib/theme-provider";

const navItems = [
  { label: "Dashboard", href: "/portal", icon: LayoutDashboard },
  { label: "Health", href: "/portal/health", icon: HeartPulse },
  { label: "Finance", href: "/portal/accounting", icon: Receipt },
  { label: "Advisory", href: "/portal/advisory", icon: Briefcase },
  { label: "Marketing", href: "/portal/marketing", icon: Megaphone },
  { label: "Connections", href: "/portal/connections", icon: Plug },
  { label: "Automations", href: "/portal/workflows", icon: Zap },
  { label: "AI Agents", href: "/portal/ai-agents", icon: Bot },
  { label: "Documents", href: "/portal/documents", icon: FileText },
  { label: "Notifications", href: "/portal/notifications", icon: Bell },
  { label: "Reports", href: "/portal/reports", icon: FileBarChart },
  { label: "WhatsApp", href: "/portal/whatsapp", icon: MessageCircle },
  { label: "Support", href: "/portal/support", icon: HeadphonesIcon },
  { label: "Billing", href: "/portal/billing", icon: CreditCard },
  { label: "Settings", href: "/portal/settings", icon: Settings },
];

export function PortalNav() {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();
  const theme = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Auto-logout after 30 minutes of inactivity
  const TIMEOUT_MS = 30 * 60 * 1000;
  const resetTimer = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(async () => {
      await supabase.auth.signOut();
      router.push("/portal/login");
    }, TIMEOUT_MS);
  }, [supabase, router, TIMEOUT_MS]);

  useEffect(() => {
    const events = ["mousedown", "keydown", "scroll", "touchstart"];
    events.forEach((e) => window.addEventListener(e, resetTimer));
    resetTimer();
    return () => {
      events.forEach((e) => window.removeEventListener(e, resetTimer));
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [resetTimer]);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/portal/login");
  }

  const isActive = (href: string) => pathname === href;

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="portal-sidebar hidden lg:flex lg:flex-col fixed top-0 left-0 bottom-0 w-[264px] bg-[#0F0F13] border-r border-[rgba(255,255,255,0.08)] z-[100]">
        {/* Brand accent line */}
        <div
          className="absolute top-0 left-0 bottom-0 w-[3px]"
          style={{ background: "var(--brand-primary)" }}
        />

        {/* Logo area */}
        <div className="flex items-center gap-3 px-6 py-6">
          {theme.logoUrl ? (
            <Image
              src={theme.logoUrl}
              alt={theme.companyName}
              width={160}
              height={36}
              className="max-h-9 max-w-[160px] object-contain"
              unoptimized
            />
          ) : (
            <div className="flex items-center gap-2">
              <Shield size={22} style={{ color: "var(--brand-primary)" }} />
              <span className="text-[15px] font-bold tracking-wide text-white">
                {theme.isCustomBranded ? theme.companyName.toUpperCase() : "ANYVISION"}
              </span>
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex-1 px-3 py-1 flex flex-col gap-0.5 overflow-y-auto">
          {navItems.map((item) => {
            const active = isActive(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                  active
                    ? "bg-[var(--brand-primary-bg)] text-white border-l-[3px] border-[var(--brand-primary)] pl-[9px]"
                    : "text-[#71717A] hover:text-[#A1A1AA] hover:bg-[rgba(255,255,255,0.03)]"
                }`}
              >
                <Icon size={18} className="flex-shrink-0" />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* System status */}
        <div className="mx-3 mb-2 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] flex items-center gap-2.5 text-xs text-[#A1A1AA]">
          <span className="pulse-dot w-2 h-2 rounded-full bg-emerald-500 inline-block flex-shrink-0" />
          All Systems Operational
        </div>

        {/* Logout */}
        <div className="px-3 py-3 border-t border-[rgba(255,255,255,0.06)]">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[#71717A] hover:text-red-400 hover:bg-red-500/5 w-full transition-colors duration-150"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[#0F0F13] border-b border-[rgba(255,255,255,0.08)] z-[100] flex items-center justify-between px-4">
        <div className="flex items-center gap-2.5">
          <div
            className="w-[3px] h-8 rounded-sm"
            style={{ background: "var(--brand-primary)" }}
          />
          <span className="text-sm font-bold tracking-wide text-white">
            {theme.isCustomBranded ? theme.companyName.toUpperCase() : "ANYVISION"}
          </span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-[#A1A1AA] p-2"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 top-14 bg-[#0F0F13] z-[90] p-4 animate-fade-in-up">
          <nav className="flex flex-col gap-0.5">
            {navItems.map((item) => {
              const active = isActive(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 px-3 py-3.5 rounded-lg text-sm font-medium ${
                    active
                      ? "bg-[var(--brand-primary-bg)] text-white border-l-[3px] border-[var(--brand-primary)] pl-[9px]"
                      : "text-[#71717A]"
                  }`}
                >
                  <Icon size={18} />
                  {item.label}
                </Link>
              );
            })}

            <div className="pt-4 mt-4 border-t border-[rgba(255,255,255,0.06)]">
              <div className="flex items-center gap-2.5 px-3 py-2.5 text-xs text-[#A1A1AA]">
                <span className="pulse-dot w-2 h-2 rounded-full bg-emerald-500 inline-block" />
                All Systems Operational
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-3 px-3 py-3.5 rounded-lg text-sm text-red-400 w-full cursor-pointer"
              >
                <LogOut size={18} />
                Sign Out
              </button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
