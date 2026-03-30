"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  User,
  Calendar,
  CheckSquare,
  FileText,
  DollarSign,
  Lightbulb,
  MessageCircle,
} from "lucide-react";

const advisoryNavItems = [
  { label: "Dashboard", href: "/portal/advisory/dashboard", icon: LayoutDashboard },
  { label: "Profile", href: "/portal/advisory/profile", icon: User },
  { label: "Meetings", href: "/portal/advisory/meetings", icon: Calendar },
  { label: "Tasks", href: "/portal/advisory/tasks", icon: CheckSquare },
  { label: "Documents", href: "/portal/advisory/documents", icon: FileText },
  { label: "Pricing", href: "/portal/advisory/pricing", icon: DollarSign },
  { label: "Insights", href: "/portal/advisory/insights", icon: Lightbulb },
  { label: "Communications", href: "/portal/advisory/communications", icon: MessageCircle },
];

export default function AdvisoryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div style={{ display: "flex", gap: "24px", minHeight: "calc(100vh - 64px)" }}>
      {/* Advisory sub-navigation sidebar */}
      <nav
        style={{
          width: "220px",
          flexShrink: 0,
          background: "rgba(255,255,255,0.03)",
          borderRadius: "16px",
          border: "1px solid rgba(255,255,255,0.06)",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          padding: "16px 8px",
          display: "flex",
          flexDirection: "column",
          gap: "2px",
          alignSelf: "flex-start",
          position: "sticky",
          top: "32px",
        }}
      >
        <div
          style={{
            padding: "8px 12px 16px 12px",
            fontSize: "11px",
            fontWeight: 700,
            letterSpacing: "1.5px",
            color: "#00A651",
            textTransform: "uppercase",
          }}
        >
          Discovery Advisory
        </div>

        {advisoryNavItems.map((item) => {
          const isActive =
            pathname === item.href ||
            (item.href !== "/portal/advisory/dashboard" &&
              pathname.startsWith(item.href));
          const Icon = item.icon;

          return (
            <Link
              key={item.href}
              href={item.href}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                padding: isActive ? "10px 12px 10px 9px" : "10px 12px",
                borderRadius: "8px",
                color: isActive ? "#fff" : "#6B7280",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
                transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                textDecoration: "none",
                background: isActive ? "rgba(108,99,255,0.15)" : "transparent",
                borderLeft: isActive ? "3px solid #00A651" : "3px solid transparent",
              }}
            >
              <Icon size={16} style={{ flexShrink: 0 }} />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Advisory content area */}
      <div style={{ flex: 1, minWidth: 0 }}>{children}</div>
    </div>
  );
}
