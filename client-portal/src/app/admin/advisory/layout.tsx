"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Users,
  GitBranch,
  Calendar,
  CheckSquare,
  ShieldCheck,
  LayoutDashboard,
  Building2,
} from "lucide-react";

const NAV_ITEMS = [
  {
    href: "/admin/advisory/my-dashboard",
    label: "My Dashboard",
    icon: LayoutDashboard,
  },
  { href: "/admin/advisory/clients", label: "Clients", icon: Users },
  { href: "/admin/advisory/pipeline", label: "Pipeline", icon: GitBranch },
  { href: "/admin/advisory/meetings", label: "Meetings", icon: Calendar },
  { href: "/admin/advisory/tasks", label: "Tasks", icon: CheckSquare },
  {
    href: "/admin/advisory/compliance",
    label: "Compliance",
    icon: ShieldCheck,
  },
  { href: "/admin/advisory/offices", label: "Offices", icon: Building2 },
];

export default function AdvisoryLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      {/* Advisory Sub-Navigation */}
      <div className="flex items-center gap-1 overflow-x-auto pb-2 scrollbar-hide">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "bg-[rgba(108,99,255,0.15)] text-[#6C63FF] border border-[rgba(108,99,255,0.3)]"
                  : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </div>

      {/* Gradient divider */}
      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(108,99,255,0.3)] to-transparent" />

      {/* Page content */}
      {children}
    </div>
  );
}
