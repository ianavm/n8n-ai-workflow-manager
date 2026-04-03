"use client";

import { usePathname, useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { useState, useEffect, useCallback, useRef } from "react";
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
} from "lucide-react";

const navItems = [
  { label: "Dashboard", href: "/portal", icon: LayoutDashboard },
  { label: "Finance", href: "/portal/accounting", icon: Receipt },
  { label: "Advisory", href: "/portal/advisory", icon: Briefcase },
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

  return (
    <>
      {/* Desktop sidebar -- V1 Command Center exact styling */}
      <aside
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          bottom: 0,
          width: "264px",
          background: "rgba(10,15,28,0.95)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          zIndex: 100,
          borderRight: "1px solid rgba(255,255,255,0.08)",
        }}
        className="hidden lg:flex lg:flex-col"
      >
        {/* Gradient stripe on left edge (V1 sidebar::before) */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            bottom: 0,
            width: "3px",
            background: "linear-gradient(180deg, #6C63FF, #00D4AA, #FF6D5A)",
          }}
        />

        {/* Logo area */}
        <div
          style={{
            padding: "28px 24px 24px 24px",
            display: "flex",
            alignItems: "center",
            gap: "12px",
          }}
        >
          {/* Orbital SVG icon from V1 preview */}
          <svg width="36" height="36" viewBox="0 0 48 48" fill="none">
            <defs>
              <linearGradient id="lgSide" x1="0" y1="0" x2="48" y2="48">
                <stop stopColor="#6C63FF" />
                <stop offset="1" stopColor="#00D4AA" />
              </linearGradient>
            </defs>
            <circle cx="24" cy="24" r="22" stroke="url(#lgSide)" strokeWidth="2" fill="none" />
            <circle cx="24" cy="24" r="14" stroke="url(#lgSide)" strokeWidth="1.5" fill="none" opacity="0.5" />
            <circle cx="24" cy="24" r="5" fill="url(#lgSide)" />
            <circle cx="24" cy="6" r="3" fill="#6C63FF" />
            <circle cx="42" cy="24" r="3" fill="#00D4AA" />
            <circle cx="24" cy="42" r="3" fill="#FF6D5A" />
          </svg>
          <span
            style={{
              fontSize: "15px",
              fontWeight: 700,
              letterSpacing: "2px",
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            ANYVISION
          </span>
        </div>

        {/* Nav items */}
        <nav
          style={{
            flex: 1,
            padding: "8px 12px",
            display: "flex",
            flexDirection: "column",
            gap: "2px",
          }}
        >
          {navItems.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <Link
                key={item.href}
                href={item.href}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: isActive ? "11px 14px 11px 11px" : "11px 14px",
                  borderRadius: "10px",
                  color: isActive ? "#fff" : "#6B7280",
                  fontSize: "14px",
                  fontWeight: 500,
                  cursor: "pointer",
                  transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                  textDecoration: "none",
                  background: isActive ? "rgba(108,99,255,0.15)" : "transparent",
                  borderLeft: isActive ? "3px solid #6C63FF" : "none",
                  fontFamily: "inherit",
                }}
                onMouseEnter={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLElement).style.color = "#B0B8C8";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isActive) {
                    (e.currentTarget as HTMLElement).style.color = "#6B7280";
                  }
                }}
              >
                <Icon size={20} style={{ flexShrink: 0 }} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        {/* System status widget */}
        <div
          style={{
            margin: "12px",
            padding: "14px 16px",
            borderRadius: "12px",
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.08)",
            display: "flex",
            alignItems: "center",
            gap: "10px",
            fontSize: "12px",
            color: "#B0B8C8",
          }}
        >
          <span
            className="pulse-dot"
            style={{
              width: "8px",
              height: "8px",
              borderRadius: "50%",
              background: "#10B981",
              flexShrink: 0,
              display: "inline-block",
            }}
          />
          All Systems Operational
        </div>

        {/* Logout */}
        <div style={{ padding: "8px 12px 12px 12px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
          <button
            onClick={handleLogout}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
              padding: "11px 14px",
              borderRadius: "10px",
              color: "#6B7280",
              fontSize: "14px",
              fontWeight: 500,
              cursor: "pointer",
              background: "none",
              border: "none",
              width: "100%",
              textAlign: "left",
              fontFamily: "inherit",
              transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
            }}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLElement).style.color = "#EF4444";
              (e.currentTarget as HTMLElement).style.background = "rgba(239,68,68,0.05)";
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLElement).style.color = "#6B7280";
              (e.currentTarget as HTMLElement).style.background = "none";
            }}
          >
            <LogOut size={20} />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Mobile header */}
      <header
        className="lg:hidden flex items-center justify-between"
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          height: "56px",
          background: "rgba(10,15,28,0.95)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          zIndex: 100,
          padding: "0 16px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <div
            style={{
              width: "3px",
              height: "32px",
              borderRadius: "2px",
              background: "linear-gradient(180deg, #6C63FF, #00D4AA, #FF6D5A)",
            }}
          />
          <span
            style={{
              fontSize: "15px",
              fontWeight: 700,
              letterSpacing: "2px",
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            ANYVISION
          </span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          style={{
            color: "#B0B8C8",
            padding: "8px",
            background: "none",
            border: "none",
            cursor: "pointer",
          }}
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X size={20} /> : <Menu size={20} />}
        </button>
      </header>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div
          className="lg:hidden animate-fade-in-up"
          style={{
            position: "fixed",
            inset: 0,
            top: "56px",
            background: "rgba(10,15,28,0.98)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            zIndex: 90,
            padding: "16px",
          }}
        >
          <nav style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
            {navItems.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileOpen(false)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "12px",
                    padding: "14px",
                    borderRadius: "10px",
                    color: isActive ? "#fff" : "#6B7280",
                    fontSize: "14px",
                    fontWeight: 500,
                    textDecoration: "none",
                    background: isActive ? "rgba(108,99,255,0.15)" : "transparent",
                    borderLeft: isActive ? "3px solid #6C63FF" : "3px solid transparent",
                  }}
                >
                  <Icon size={20} />
                  {item.label}
                </Link>
              );
            })}

            {/* Status + logout */}
            <div style={{ paddingTop: "16px", marginTop: "16px", borderTop: "1px solid rgba(255,255,255,0.08)" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px", padding: "10px 14px", fontSize: "12px", color: "#B0B8C8" }}>
                <span className="pulse-dot" style={{ width: "8px", height: "8px", borderRadius: "50%", background: "#10B981", display: "inline-block" }} />
                All Systems Operational
              </div>
              <button
                onClick={handleLogout}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  padding: "14px",
                  borderRadius: "10px",
                  color: "#EF4444",
                  fontSize: "14px",
                  fontWeight: 500,
                  background: "none",
                  border: "none",
                  width: "100%",
                  textAlign: "left",
                  fontFamily: "inherit",
                  cursor: "pointer",
                }}
              >
                <LogOut size={20} />
                Sign Out
              </button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
