"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, Users, UserPlus } from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin/marketing", label: "Overview", icon: LayoutDashboard, exact: true },
  { href: "/admin/marketing/clients", label: "Clients", icon: Users },
  { href: "/admin/marketing/onboarding", label: "Onboarding", icon: UserPlus },
];

export default function MarketingAdminLayout({
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
