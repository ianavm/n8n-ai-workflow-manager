"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  FileText,
  Receipt,
  ArrowLeftRight,
  CheckSquare,
  ListTodo,
  ScrollText,
  BarChart3,
  Settings,
  Package,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/admin/accounting", label: "Dashboard", icon: LayoutDashboard, exact: true },
  { href: "/admin/accounting/invoices", label: "Invoices", icon: FileText },
  { href: "/admin/accounting/bills", label: "Supplier Bills", icon: Package },
  { href: "/admin/accounting/reconciliation", label: "Reconciliation", icon: ArrowLeftRight },
  { href: "/admin/accounting/approvals", label: "Approvals", icon: CheckSquare },
  { href: "/admin/accounting/tasks", label: "Tasks", icon: ListTodo },
  { href: "/admin/accounting/audit", label: "Audit Trail", icon: ScrollText },
  { href: "/admin/accounting/reports", label: "Reports", icon: BarChart3 },
  { href: "/admin/accounting/settings", label: "Settings", icon: Settings },
];

export default function AccountingLayout({
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
                  ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] border border-[rgba(255,109,90,0.3)]"
                  : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
              }`}
            >
              <Icon size={16} />
              {label}
            </Link>
          );
        })}
      </div>

      <div className="h-px bg-gradient-to-r from-transparent via-[rgba(255,109,90,0.3)] to-transparent" />

      {children}
    </div>
  );
}
