"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Target,
  FileText,
  CalendarDays,
  Users,
  MessageCircle,
  BarChart3,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/portal/marketing", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/portal/marketing/campaigns", label: "Campaigns", icon: Target },
  { href: "/portal/marketing/content", label: "Content", icon: FileText },
  { href: "/portal/marketing/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/portal/marketing/leads", label: "Leads", icon: Users },
  { href: "/portal/marketing/conversations", label: "Conversations", icon: MessageCircle },
  { href: "/portal/marketing/reports", label: "Reports", icon: BarChart3 },
];

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 overflow-x-auto pb-2 scrollbar-hide">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const isActive = exact
            ? pathname === href
            : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.3)]"
                  : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </div>

      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(16,185,129,0.3)] to-transparent" />

      {children}
    </div>
  );
}
