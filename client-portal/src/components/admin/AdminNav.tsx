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
  Shield,
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
      <aside className="admin-sidebar bg-[#0F0F13] border-r border-[rgba(255,255,255,0.08)]">
        <div className="flex items-center gap-2.5 px-4 py-5 border-b border-[rgba(255,255,255,0.06)]">
          <Shield size={22} className="text-[#6366F1]" />
          <span className="text-sm font-bold text-white">
            AnyVision<span className="text-[#10B981]">.</span>
            <span className="text-[#71717A] font-normal ml-1">Admin</span>
          </span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-0.5">
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
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? "bg-[rgba(99,102,241,0.1)] text-[#6366F1] border-l-[3px] border-[#6366F1] pl-[9px]"
                    : "text-[#71717A] hover:text-[#A1A1AA] hover:bg-[rgba(255,255,255,0.03)]"
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
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-[#71717A] hover:text-red-400 hover:bg-red-500/5 w-full transition-colors duration-150"
          >
            <LogOut size={18} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <header className="lg:hidden fixed top-0 left-0 right-0 h-14 bg-[#0F0F13] border-b border-[rgba(255,255,255,0.08)] z-40 flex items-center justify-between px-4">
        <div className="flex items-center gap-2">
          <Shield size={18} className="text-[#6366F1]" />
          <span className="text-sm font-bold text-white">
            AnyVision<span className="text-[#10B981]">.</span> Admin
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

      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 top-14 bg-[#0F0F13] z-30 p-4 animate-fade-in-up">
          <nav className="space-y-0.5">
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
                      ? "bg-[rgba(99,102,241,0.1)] text-[#6366F1]"
                      : "text-[#71717A]"
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
