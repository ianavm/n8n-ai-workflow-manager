"use client";

import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useState } from "react";
import Link from "next/link";
import {
  LayoutDashboard,
  Users,
  BarChart3,
  Settings,
  Activity,
  LogOut,
  Menu,
  X,
  Bot,
  HeadphonesIcon,
  HeartPulse,
  Calculator,
  Megaphone,
} from "lucide-react";

const navItems = [
  { label: "Overview", href: "/admin", icon: LayoutDashboard },
  { label: "Accounting", href: "/admin/accounting", icon: Calculator },
  { label: "Marketing", href: "/admin/marketing", icon: Megaphone },
  { label: "AI Agents", href: "/admin/agents", icon: Bot },
  { label: "Client Health", href: "/admin/health", icon: HeartPulse },
  { label: "Clients", href: "/admin/clients", icon: Users },
  { label: "Support", href: "/admin/support", icon: HeadphonesIcon },
  { label: "Analytics", href: "/admin/analytics", icon: BarChart3 },
  { label: "Management", href: "/admin/management", icon: Settings },
  { label: "Activity Log", href: "/admin/activity", icon: Activity },
];

export function AdminNav() {
  const pathname = usePathname();
  const router = useRouter();
  const supabase = createClient();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function handleLogout() {
    await supabase.auth.signOut();
    router.push("/admin/login");
  }

  return (
    <>
      {/* Desktop sidebar */}
      <aside className="admin-sidebar bg-[rgba(0,0,0,0.3)] backdrop-blur-xl border-r border-[rgba(255,255,255,0.06)]">
        <div className="flex items-center gap-2 px-4 py-5 border-b border-[rgba(255,255,255,0.06)]">
          <svg viewBox="0 0 200 200" width="28" height="28" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="aNavGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6C63FF" /><stop offset="100%" stopColor="#00D4AA" />
              </linearGradient>
            </defs>
            <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#aNavGrad)" opacity="0.10" />
            <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#aNavGrad)" strokeWidth="8" strokeLinejoin="round" />
            <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
          </svg>
          <span className="text-sm font-bold text-white">
            AnyVision<span className="text-[#00D4AA]">.</span>
            <span className="text-[#6B7280] font-normal ml-1">Admin</span>
          </span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {navItems.map((item) => {
            const isActive =
              item.href === "/admin"
                ? pathname === "/admin"
                : pathname.startsWith(item.href);
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive
                    ? "bg-[rgba(108,99,255,0.12)] text-[#6C63FF] border-l-[3px] border-[#6C63FF] ml-0 pl-[9px]"
                    : "text-[#6B7280] hover:text-[#B0B8C8] hover:bg-[rgba(255,255,255,0.03)] hover:translate-x-0.5"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="px-3 py-4 border-t border-[rgba(255,255,255,0.06)]">
          <button
            onClick={handleLogout}
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[#6B7280] hover:text-red-400 hover:bg-red-500/5 w-full transition-all duration-200"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[rgba(0,0,0,0.4)] backdrop-blur-xl border-b border-[rgba(255,255,255,0.06)] z-40 flex items-center justify-between px-4">
        <span className="text-sm font-bold text-white">
          AnyVision<span className="text-[#00D4AA]">.</span> Admin
        </span>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="text-[#B0B8C8] p-2"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 top-14 bg-[rgba(0,0,0,0.6)] backdrop-blur-xl z-30 p-4 animate-fade-in-up" style={{ animationDuration: "0.2s" }}>
          <nav className="space-y-1">
            {navItems.map((item, i) => {
              const isActive =
                item.href === "/admin"
                  ? pathname === "/admin"
                  : pathname.startsWith(item.href);
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  className={`flex items-center gap-3 px-3 py-3 rounded-lg text-sm font-medium animate-fade-in-up ${
                    isActive
                      ? "bg-[rgba(108,99,255,0.12)] text-[#6C63FF]"
                      : "text-[#6B7280]"
                  }`}
                  style={{ animationDelay: `${i * 0.04}s` }}
                >
                  <Icon size={18} />
                  {item.label}
                </Link>
              );
            })}
            <button
              onClick={handleLogout}
              className="flex items-center gap-3 px-3 py-3 rounded-lg text-sm text-red-400 w-full mt-4 animate-fade-in-up"
              style={{ animationDelay: `${navItems.length * 0.04}s` }}
            >
              <LogOut size={18} />
              Sign Out
            </button>
          </nav>
        </div>
      )}
    </>
  );
}
