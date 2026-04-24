import {
  Bell,
  Bot,
  Briefcase,
  CreditCard,
  FileBarChart,
  FileText,
  HeadphonesIcon,
  HeartPulse,
  LayoutDashboard,
  type LucideIcon,
  Megaphone,
  MessageCircle,
  Plug,
  Receipt,
  Settings,
  Target,
  Zap,
} from "lucide-react";

export interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  /** Used by CommandPalette for fuzzy-matching. */
  keywords?: string[];
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", href: "/portal",        icon: LayoutDashboard, keywords: ["home", "kpi", "metrics"] },
      { label: "Health",    href: "/portal/health", icon: HeartPulse,      keywords: ["score", "risk", "status"] },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Automations",  href: "/portal/workflows",   icon: Zap,          keywords: ["workflow", "flows", "triggers"] },
      { label: "AI Agents",    href: "/portal/ai-agents",   icon: Bot,          keywords: ["agents", "llm", "bots"] },
      { label: "Connections",  href: "/portal/connections", icon: Plug,         keywords: ["integrations", "apis"] },
      { label: "Documents",    href: "/portal/documents",   icon: FileText,     keywords: ["files", "storage"] },
      { label: "WhatsApp",     href: "/portal/whatsapp",    icon: MessageCircle,keywords: ["chat", "messages", "inbox"] },
    ],
  },
  {
    label: "Growth",
    items: [
      { label: "CRM",        href: "/portal/crm",       icon: Target,    keywords: ["leads", "pipeline", "deals"] },
      { label: "Marketing",  href: "/portal/marketing", icon: Megaphone, keywords: ["ads", "campaigns", "spend"] },
      { label: "Advisory",   href: "/portal/advisory",  icon: Briefcase, keywords: ["meetings", "proposals"] },
    ],
  },
  {
    label: "Finance",
    items: [
      { label: "Accounting", href: "/portal/accounting", icon: Receipt,     keywords: ["invoices", "payments"] },
      { label: "Billing",    href: "/portal/billing",    icon: CreditCard,  keywords: ["subscription", "plan", "upgrade"] },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Notifications", href: "/portal/notifications", icon: Bell,           keywords: ["alerts", "inbox"] },
      { label: "Reports",       href: "/portal/reports",       icon: FileBarChart,   keywords: ["analytics", "export"] },
      { label: "Support",       href: "/portal/support",       icon: HeadphonesIcon, keywords: ["help", "ticket"] },
      { label: "Settings",      href: "/portal/settings",      icon: Settings,       keywords: ["preferences", "profile", "account"] },
    ],
  },
];

/** Flattened list — consumed by CommandPalette. */
export const NAV_ITEMS_FLAT: NavItem[] = NAV_GROUPS.flatMap((g) => g.items);

/** Return the nav item matching the current path, if any. */
export function findActiveNavItem(pathname: string): NavItem | undefined {
  // Exact match first, then longest prefix match so sub-routes highlight the parent.
  const exact = NAV_ITEMS_FLAT.find((n) => n.href === pathname);
  if (exact) return exact;
  return NAV_ITEMS_FLAT.filter((n) => n.href !== "/portal" && pathname.startsWith(n.href + "/"))
    .sort((a, b) => b.href.length - a.href.length)[0];
}
