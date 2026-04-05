"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { AnimatedNumber } from "@/components/dashboard/AnimatedNumber";
import { SparkLine } from "@/components/dashboard/SparkLine";
import { MiniGauge } from "@/components/dashboard/MiniGauge";
import { ComparisonArrow } from "@/components/dashboard/ComparisonArrow";
import { ActivityFeedItem } from "@/components/dashboard/ActivityFeedItem";
import { ModuleQuickCard } from "@/components/dashboard/ModuleQuickCard";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  DollarSign,
  UserPlus,
  Target,
  BarChart3,
  Send,
  CheckCircle,
  AlertTriangle,
  AlertCircle,
  Info,
} from "lucide-react";
import Link from "next/link";
import { TrialProgress } from "@/components/dashboard/TrialProgress";

interface KPI {
  value: number;
  change_pct: number;
  sparkline: number[];
}

interface DashboardData {
  profile: { full_name: string; company_name: string | null };
  kpis: {
    total_revenue: KPI;
    new_leads: KPI;
    ad_spend: KPI;
    active_campaigns: KPI;
    messages_sent: KPI;
    success_rate: KPI;
  };
  health: { composite_score: number; usage_score: number; payment_score: number; engagement_score: number; support_score: number; risk_level: string; trend: string } | null;
  modules: { marketing: boolean; accounting: boolean };
  module_summaries: {
    marketing?: { active_campaigns: number; spend_today: number; leads_today: number };
    accounting?: { receivables: number; payables: number; overdue_count: number };
  };
  activity_feed: Array<{ id: string; type: string; message: string; created_at: string }>;
  top_campaigns: Array<{ id: string; name: string; platform: string; budget_spent: number; status: string }>;
  hot_leads: Array<{ id: string; first_name: string | null; last_name: string | null; email: string | null; source: string; score: number; created_at: string }>;
  alerts: Array<{ id: string; alert_type: string; severity: string; message: string; created_at: string }>;
  subscription: { plan_name: string; status: string; trial_end: string | null } | null;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

const KPI_CONFIG = [
  { key: "total_revenue" as const, label: "TOTAL REVENUE", icon: DollarSign, color: "#00D4AA", prefix: "R", decimals: 0, href: "/portal/accounting", isCents: true },
  { key: "new_leads" as const, label: "NEW LEADS", icon: UserPlus, color: "#10B981", href: "/portal/marketing/leads" },
  { key: "ad_spend" as const, label: "AD SPEND", icon: Target, color: "#FF6D5A", prefix: "R", href: "/portal/marketing", isCents: true },
  { key: "active_campaigns" as const, label: "CAMPAIGNS", icon: BarChart3, color: "#F59E0B", href: "/portal/marketing/campaigns" },
  { key: "messages_sent" as const, label: "MESSAGES SENT", icon: Send, color: "#6C63FF", href: "/portal/whatsapp" },
  { key: "success_rate" as const, label: "SUCCESS RATE", icon: CheckCircle, color: "#00D4AA", suffix: "%", decimals: 1, href: "/portal/workflows" },
];

const PERFORMER_TABS = ["Campaigns", "Leads"] as const;

export default function PortalDashboard() {
  const router = useRouter();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState("30d");
  const [performerTab, setPerformerTab] = useState<(typeof PERFORMER_TABS)[number]>("Campaigns");

  const loadData = useCallback(async (p: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/portal/dashboard/unified?period=${p}`);
      if (res.ok) setData(await res.json());
    } catch { /* silent */ }
    setLoading(false);
  }, []);

  useEffect(() => { loadData(period); }, [period, loadData]);

  if (loading && !data) {
    return (
      <div className="space-y-8">
        <Skeleton className="h-24 w-full" />
        <div className="kpi-comparison-grid">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-40" />)}
        </div>
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-80 w-full" />
      </div>
    );
  }

  if (!data) return null;

  const today = new Date().toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

  return (
    <div className="space-y-8">
      {/* Section 1: Hero Welcome */}
      <div className="dashboard-section">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-white">
              {getGreeting()}, {data.profile.full_name?.split(" ")[0] ?? "there"}
            </h1>
            <p className="text-sm text-[#6B7280] mt-1">{today}</p>
            <div className="flex items-center gap-3 mt-3 text-sm text-[#B0B8C8] flex-wrap">
              <span className="flex items-center gap-1.5">
                <AnimatedNumber value={data.kpis.total_revenue.value / 100} prefix="R" decimals={0} />
                <span className="text-[#6B7280]">revenue</span>
              </span>
              <span className="text-[#6B7280]">&middot;</span>
              <span className="flex items-center gap-1.5">
                <AnimatedNumber value={data.kpis.new_leads.value} />
                <span className="text-[#6B7280]">new leads</span>
              </span>
              <span className="text-[#6B7280]">&middot;</span>
              <span className="flex items-center gap-1.5">
                <AnimatedNumber value={data.kpis.success_rate.value} suffix="%" decimals={1} />
                <span className="text-[#6B7280]">uptime</span>
              </span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {["7d", "30d", "90d"].map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  period === p
                    ? "bg-[var(--brand-primary-bg,rgba(108,99,255,0.15))] text-[var(--brand-primary,#6C63FF)] border border-[var(--brand-primary-glow,rgba(108,99,255,0.3))]"
                    : "text-[#6B7280] hover:text-[#B0B8C8] hover:bg-[rgba(255,255,255,0.05)]"
                }`}
              >
                {p.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Trial Progress + Achievement Checklist */}
      <TrialProgress
        trialEnd={data.subscription?.trial_end ?? null}
        subscriptionStatus={data.subscription?.status ?? null}
      />

      {/* Section 2: KPI Comparison Row */}
      <div className="dashboard-section kpi-comparison-grid">
        {KPI_CONFIG.map(({ key, label, icon: Icon, color, prefix, suffix, decimals, href, isCents }) => {
          const kpi = data.kpis[key];
          const displayValue = isCents ? kpi.value / 100 : kpi.value;
          return (
            <div
              key={key}
              onClick={() => router.push(href)}
              className="floating-card p-5 cursor-pointer group"
            >
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-3"
                style={{ background: `${color}15`, color }}
              >
                <Icon size={20} />
              </div>
              <p className="text-[10px] text-[#6B7280] uppercase tracking-wider font-semibold mb-1">{label}</p>
              <div className="stat-number-shimmer text-2xl mb-1">
                <AnimatedNumber value={displayValue} prefix={prefix} suffix={suffix} decimals={decimals ?? 0} />
              </div>
              <ComparisonArrow value={kpi.change_pct} size="sm" />
              <div className="mt-3 opacity-60 group-hover:opacity-100 transition-opacity">
                <SparkLine data={kpi.sparkline} color={color} height={28} />
              </div>
            </div>
          );
        })}
      </div>

      {/* Section 3: Business Health Meter */}
      {data.health ? (
        <div className="dashboard-section glass-card p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-4">
              <div className="text-3xl font-bold text-white">
                <AnimatedNumber value={data.health.composite_score} />
              </div>
              <RiskBadge level={data.health.risk_level as "low" | "medium" | "high" | "critical"} />
            </div>
            <Link href="/portal/health" className="text-sm text-[var(--brand-primary,#6C63FF)] hover:underline">
              View Details &rarr;
            </Link>
          </div>
          <div className="h-3 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden mb-5">
            <div
              className="h-full rounded-full health-bar-gradient transition-all duration-1000 ease-out"
              style={{ width: `${data.health.composite_score}%` }}
            />
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MiniGauge score={data.health.usage_score} label="Usage" />
            <MiniGauge score={data.health.payment_score} label="Payment" />
            <MiniGauge score={data.health.engagement_score} label="Engagement" />
            <MiniGauge score={data.health.support_score} label="Support" />
          </div>
        </div>
      ) : (
        <div className="dashboard-section glass-card p-6 text-center">
          <p className="text-sm text-[#6B7280]">Health scoring will be available once you have 7 days of activity data.</p>
        </div>
      )}

      {/* Section 4: Performance + Activity Feed */}
      <div className="dashboard-section revenue-activity-grid">
        <div className="floating-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Performance Overview</h2>
          <div className="grid grid-cols-2 gap-3">
            {[
              { label: "Revenue", value: formatZAR(data.kpis.total_revenue.value), color: "#00D4AA" },
              { label: "Ad Spend", value: formatZAR(data.kpis.ad_spend.value), color: "#FF6D5A" },
              { label: "Leads", value: String(data.kpis.new_leads.value), color: "#10B981" },
              { label: "Messages", value: String(data.kpis.messages_sent.value), color: "#6C63FF" },
            ].map((m) => (
              <div key={m.label} className="p-3 rounded-lg bg-[rgba(255,255,255,0.03)]">
                <p className="text-[10px] text-[#6B7280] uppercase tracking-wider">{m.label}</p>
                <p className="text-lg font-semibold text-white mt-1">{m.value}</p>
              </div>
            ))}
          </div>
        </div>
        <div className="floating-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Recent Activity</h2>
          <div className="space-y-1 max-h-[300px] overflow-y-auto">
            {data.activity_feed.length === 0 ? (
              <p className="text-sm text-[#6B7280]">No recent activity</p>
            ) : (
              data.activity_feed.slice(0, 10).map((e, i) => (
                <ActivityFeedItem key={e.id} type={e.type} message={e.message} timestamp={e.created_at} index={i} />
              ))
            )}
          </div>
        </div>
      </div>

      {/* Section 5: Module Quick Cards */}
      {(data.modules.marketing || data.modules.accounting) && (
        <div className="dashboard-section">
          <h2 className="text-base font-semibold text-white mb-4">Active Modules</h2>
          <div className="module-scroll-row">
            {data.modules.marketing && data.module_summaries.marketing && (
              <ModuleQuickCard
                module="marketing"
                metrics={{
                  "Campaigns": data.module_summaries.marketing.active_campaigns,
                  "Leads Today": data.module_summaries.marketing.leads_today,
                  "Spend": formatZAR(data.module_summaries.marketing.spend_today),
                }}
                href="/portal/marketing"
              />
            )}
            {data.modules.accounting && data.module_summaries.accounting && (
              <ModuleQuickCard
                module="accounting"
                metrics={{
                  "Receivables": formatZAR(data.module_summaries.accounting.receivables),
                  "Payables": formatZAR(data.module_summaries.accounting.payables),
                  "Overdue": data.module_summaries.accounting.overdue_count,
                }}
                href="/portal/accounting"
              />
            )}
          </div>
        </div>
      )}

      {/* Section 6: Top Performers */}
      {(data.top_campaigns.length > 0 || data.hot_leads.length > 0) && (
        <div className="dashboard-section floating-card p-6">
          <div className="flex items-center gap-2 mb-4">
            {PERFORMER_TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setPerformerTab(tab)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                  performerTab === tab
                    ? "bg-[var(--brand-primary-bg,rgba(108,99,255,0.15))] text-[var(--brand-primary,#6C63FF)]"
                    : "text-[#6B7280] hover:text-[#B0B8C8]"
                }`}
              >
                {tab}
              </button>
            ))}
          </div>
          {performerTab === "Campaigns" ? (
            <div className="space-y-2">
              {data.top_campaigns.length === 0 ? (
                <p className="text-sm text-[#6B7280]">No campaigns yet</p>
              ) : (
                data.top_campaigns.map((c) => (
                  <Link key={c.id} href={`/portal/marketing/campaigns/${c.id}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors">
                    <span className="text-sm text-white">{c.name}</span>
                    <span className="text-xs text-[#B0B8C8]">{formatZAR(c.budget_spent)} spent</span>
                  </Link>
                ))
              )}
            </div>
          ) : (
            <div className="space-y-2">
              {data.hot_leads.length === 0 ? (
                <p className="text-sm text-[#6B7280]">No hot leads yet</p>
              ) : (
                data.hot_leads.map((l) => (
                  <Link key={l.id} href={`/portal/marketing/leads/${l.id}`} className="flex items-center justify-between p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors">
                    <span className="text-sm text-white">{[l.first_name, l.last_name].filter(Boolean).join(" ") || l.email || "Unknown"}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full" style={{ background: l.score >= 70 ? "rgba(16,185,129,0.12)" : "rgba(234,179,8,0.12)", color: l.score >= 70 ? "#10B981" : "#EAB308" }}>{l.score}</span>
                  </Link>
                ))
              )}
            </div>
          )}
        </div>
      )}

      {/* Section 7: Alerts */}
      {data.alerts.length > 0 && (
        <div className="dashboard-section floating-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-base font-semibold text-white">Active Alerts</h2>
            <span className="px-2 py-0.5 rounded-full text-xs font-semibold bg-[rgba(239,68,68,0.12)] text-[#EF4444]">{data.alerts.length}</span>
          </div>
          <div className="space-y-2">
            {data.alerts.map((a) => {
              const SevIcon = a.severity === "critical" || a.severity === "high" ? AlertTriangle : a.severity === "medium" ? AlertCircle : Info;
              const sevColor = a.severity === "critical" ? "#EF4444" : a.severity === "high" ? "#F97316" : a.severity === "medium" ? "#EAB308" : "#6B7280";
              return (
                <div key={a.id} className="flex items-start gap-3 p-3 rounded-lg" style={{ background: `${sevColor}08` }}>
                  <SevIcon size={16} style={{ color: sevColor, marginTop: 2, flexShrink: 0 }} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-[#B0B8C8]">{a.message}</p>
                    <p className="text-[10px] text-[#6B7280] mt-1">{new Date(a.created_at).toLocaleDateString("en-ZA")}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
