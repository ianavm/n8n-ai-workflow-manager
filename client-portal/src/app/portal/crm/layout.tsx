"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Users,
  KanbanSquare,
  Mail,
  Workflow,
  Upload,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/portal/crm", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/portal/crm/leads", label: "Leads", icon: Users },
  { href: "/portal/crm/pipeline", label: "Pipeline", icon: KanbanSquare },
  { href: "/portal/crm/communications", label: "Communications", icon: Mail },
  { href: "/portal/crm/agents", label: "Agents", icon: Workflow },
  { href: "/portal/crm/imports", label: "Imports", icon: Upload },
  { href: "/portal/crm/settings", label: "Settings", icon: Settings },
];

const ACCENT = "#FF6D5A";

export default function CrmLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-1 overflow-x-auto pb-2 scrollbar-hide">
        {NAV_ITEMS.map(({ href, label, icon: Icon, exact }) => {
          const isActive = exact ? pathname === href : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "text-white border"
                  : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
              }`}
              style={
                isActive
                  ? {
                      background: "rgba(255,109,90,0.15)",
                      borderColor: "rgba(255,109,90,0.3)",
                      color: ACCENT,
                    }
                  : undefined
              }
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </div>

      <div
        className="h-px"
        style={{
          background:
            "linear-gradient(to right, transparent, rgba(255,109,90,0.3), transparent)",
        }}
      />

      {children}
    </div>
  );
}
