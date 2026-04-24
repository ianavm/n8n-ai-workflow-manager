"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertCircle,
  AlertTriangle,
  ArrowUpRight,
  BarChart3,
  CheckCircle,
  DollarSign,
  HeartPulse,
  Info,
  Send,
  Target,
  UserPlus,
} from "lucide-react";

import { useBrand } from "@/lib/providers/BrandProvider";
import { AnimatedNumber } from "@/components/dashboard/AnimatedNumber";
import { SparkLine } from "@/components/dashboard/SparkLine";
import { TrialProgress } from "@/components/dashboard/TrialProgress";
import { ActivityFeedItem } from "@/components/dashboard/ActivityFeedItem";

import { PageHeader } from "@/components/portal/PageHeader";
import { KPIGrid } from "@/components/portal/KPIGrid";
import { StatCard } from "@/components/portal/StatCard";
import { PeriodPicker, type Period } from "@/components/portal/PeriodPicker";
import { RiskBadge } from "@/components/portal/RiskBadge";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui-shadcn/card";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { ScrollArea } from "@/components/ui-shadcn/scroll-area";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui-shadcn/tabs";

import { HealthGauge } from "@/components/dashboard/HealthGauge";

interface KPI {
  value: number;
  change_pct: number | null;
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
  health: {
    composite_score: number;
    usage_score: number;
    payment_score: number;
    engagement_score: number;
    support_score: number;
    risk_level: string;
    trend: string;
  } | null;
  modules: { marketing: boolean; accounting: boolean };
  module_summaries: {
    marketing?: { active_campaigns: number; spend_today: number; leads_today: number };
    accounting?: { receivables: number; payables: number; overdue_count: number };
  };
  activity_feed: Array<{ id: string; type: string; message: string; created_at: string }>;
  top_campaigns: Array<{ id: string; name: string; platform: string; budget_spent: number; status: string }>;
  hot_leads: Array<{
    id: string;
    first_name: string | null;
    last_name: string | null;
    email: string | null;
    source: string;
    score: number;
    created_at: string;
  }>;
  alerts: Array<{ id: string; alert_type: string; severity: string; message: string; created_at: string }>;
  subscription: { plan_name: string; status: string; trial_end: string | null } | null;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

type AccentColor = "teal" | "coral" | "purple" | "warning" | "neutral";

type KPIKey = keyof DashboardData["kpis"];

const KPI_CONFIG: Array<{
  key: KPIKey;
  label: string;
  icon: typeof DollarSign;
  accent: AccentColor;
  sparklineColor: "teal" | "coral" | "purple" | "warning" | "brand";
  prefix?: string;
  suffix?: string;
  decimals?: number;
  href: string;
  isCents?: boolean;
  gradient?: boolean;
  cardAccent?: "purple" | "teal" | "coral" | "gradient" | "none";
}> = [
  { key: "total_revenue",    label: "Total revenue",    icon: DollarSign,  accent: "teal",    sparklineColor: "teal",    prefix: "R", decimals: 0, isCents: true,  href: "/portal/accounting", gradient: true, cardAccent: "coral" },
  { key: "new_leads",        label: "New leads",        icon: UserPlus,    accent: "teal",    sparklineColor: "teal",                            href: "/portal/crm" },
  { key: "ad_spend",         label: "Ad spend",         icon: Target,      accent: "coral",   sparklineColor: "coral",   prefix: "R", decimals: 0, isCents: true,  href: "/portal/marketing" },
  { key: "active_campaigns", label: "Active campaigns", icon: BarChart3,   accent: "warning", sparklineColor: "warning",                          href: "/portal/marketing" },
  { key: "messages_sent",    label: "Messages sent",    icon: Send,        accent: "purple",  sparklineColor: "purple",                           href: "/portal/whatsapp" },
  { key: "success_rate",     label: "Success rate",     icon: CheckCircle, accent: "teal",    sparklineColor: "teal",    suffix: "%", decimals: 1, href: "/portal/workflows" },
];

function severityConfig(severity: string) {
  switch (severity) {
    case "critical":
      return { Icon: AlertTriangle, tone: "danger",  label: "Critical" } as const;
    case "high":
      return { Icon: AlertTriangle, tone: "warning", label: "High" } as const;
    case "medium":
      return { Icon: AlertCircle,   tone: "warning", label: "Medium" } as const;
    default:
      return { Icon: Info,          tone: "info",    label: severity } as const;
  }
}

export default function PortalDashboard() {
  const { companyName } = useBrand();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState<Period>("30d");

  const loadData = useCallback(async (p: Period) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/portal/dashboard/unified?period=${p}`);
      if (res.ok) setData(await res.json());
    } catch {
      /* silent */
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData(period);
  }, [period, loadData]);

  if (loading && !data) {
    return <LoadingState variant="dashboard" />;
  }
  if (!data) return null;

  const firstName = data.profile.full_name?.split(" ")[0] ?? "there";
  const today = new Date().toLocaleDateString("en-ZA", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <div className="flex flex-col gap-8">
      {/* Hero */}
      <PageHeader
        hero
        eyebrow={today}
        title={`${greeting()}, ${firstName}`}
        description={`Welcome back to ${companyName ?? "your"} portal. Here's what's been happening across your business.`}
        actions={<PeriodPicker value={period} onChange={setPeriod} />}
      />

      {/* Trial progress */}
      <TrialProgress
        trialEnd={data.subscription?.trial_end ?? null}
        subscriptionStatus={data.subscription?.status ?? null}
      />

      {/* KPI row */}
      <KPIGrid cols={6}>
        {KPI_CONFIG.map((cfg) => {
          const kpi = data.kpis[cfg.key];
          const displayValue = cfg.isCents ? kpi.value / 100 : kpi.value;
          const Icon = cfg.icon;
          return (
            <StatCard
              key={cfg.key}
              label={cfg.label}
              value={displayValue}
              prefix={cfg.prefix}
              suffix={cfg.suffix}
              decimals={cfg.decimals ?? 0}
              delta={kpi.change_pct ?? undefined}
              accent={cfg.accent}
              cardAccent={cfg.cardAccent ?? (cfg.key === "total_revenue" ? "coral" : "none")}
              icon={<Icon className="size-4" aria-hidden />}
              sparkline={<SparkLine data={kpi.sparkline} color={cfg.sparklineColor} width={96} height={28} />}
              href={cfg.href}
              gradientNumber={cfg.gradient}
            />
          );
        })}
      </KPIGrid>

      {/* Health + Activity row */}
      <section className="grid gap-5 lg:grid-cols-5">
        {/* Health widget */}
        <Card variant="default" accent="gradient-static" padding="lg" className="lg:col-span-2 flex flex-col gap-5">
          <CardHeader>
            <div className="flex items-start justify-between gap-3">
              <div>
                <CardTitle className="text-base flex items-center gap-2">
                  <HeartPulse className="size-4 text-[var(--accent-coral)]" aria-hidden />
                  Business health
                </CardTitle>
                <CardDescription className="mt-1">
                  Composite score across usage, payment, engagement, and support.
                </CardDescription>
              </div>
              {data.health ? (
                <RiskBadge level={data.health.risk_level as "low" | "medium" | "high" | "critical"} size="sm" />
              ) : null}
            </div>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-5 pt-2">
            {data.health ? (
              <>
                <HealthGauge
                  score={data.health.composite_score}
                  size="lg"
                  showBreakdown
                  breakdownScores={{
                    usage: data.health.usage_score,
                    payment: data.health.payment_score,
                    engagement: data.health.engagement_score,
                    support: data.health.support_score,
                  }}
                />
                <Button asChild variant="ghost" size="sm" className="gap-1 self-center">
                  <Link href="/portal/health">
                    View details
                    <ArrowUpRight className="size-3.5" />
                  </Link>
                </Button>
              </>
            ) : (
              <EmptyState
                inline
                icon={<HeartPulse className="size-5" />}
                title="Scoring starts soon"
                description="Health scoring unlocks once you have 7 days of activity data."
              />
            )}
          </CardContent>
        </Card>

        {/* Activity feed */}
        <Card variant="default" padding="lg" className="lg:col-span-3 flex flex-col gap-3">
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Recent activity</CardTitle>
              <Badge tone="neutral" appearance="soft" size="sm">
                {data.activity_feed.length} events
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            {data.activity_feed.length === 0 ? (
              <EmptyState
                inline
                title="Nothing here yet"
                description="Workflow events and lead activity will appear here as they happen."
              />
            ) : (
              <ScrollArea className="h-[320px] pr-3">
                <ul className="flex flex-col gap-2">
                  {data.activity_feed.slice(0, 12).map((e, i) => (
                    <li key={e.id}>
                      <ActivityFeedItem
                        type={e.type}
                        message={e.message}
                        timestamp={e.created_at}
                        index={i}
                      />
                    </li>
                  ))}
                </ul>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </section>

      {/* Module summaries */}
      {(data.modules.marketing || data.modules.accounting) ? (
        <section className="grid gap-4 md:grid-cols-2">
          {data.modules.marketing && data.module_summaries.marketing ? (
            <Link href="/portal/marketing" className="group">
              <Card variant="interactive" accent="purple" padding="lg" className="flex flex-col gap-4">
                <CardHeader>
                  <CardTitle className="text-base">Marketing</CardTitle>
                  <CardDescription>Active campaigns + today&rsquo;s numbers</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-3 gap-3">
                  <ModuleMetric label="Campaigns" value={data.module_summaries.marketing.active_campaigns} />
                  <ModuleMetric label="Leads today" value={data.module_summaries.marketing.leads_today} />
                  <ModuleMetric label="Spend" value={formatZAR(data.module_summaries.marketing.spend_today)} />
                </CardContent>
              </Card>
            </Link>
          ) : null}
          {data.modules.accounting && data.module_summaries.accounting ? (
            <Link href="/portal/accounting" className="group">
              <Card variant="interactive" accent="teal" padding="lg" className="flex flex-col gap-4">
                <CardHeader>
                  <CardTitle className="text-base">Accounting</CardTitle>
                  <CardDescription>Receivables, payables, and overdue</CardDescription>
                </CardHeader>
                <CardContent className="grid grid-cols-3 gap-3">
                  <ModuleMetric label="Receivables" value={formatZAR(data.module_summaries.accounting.receivables)} />
                  <ModuleMetric label="Payables"    value={formatZAR(data.module_summaries.accounting.payables)} />
                  <ModuleMetric label="Overdue"     value={data.module_summaries.accounting.overdue_count} />
                </CardContent>
              </Card>
            </Link>
          ) : null}
        </section>
      ) : null}

      {/* Top performers */}
      {data.top_campaigns.length > 0 || data.hot_leads.length > 0 ? (
        <Card variant="default" padding="lg">
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Top performers</CardTitle>
          </CardHeader>
          <CardContent>
            <Tabs defaultValue="campaigns">
              <TabsList variant="ghost" className="mb-4">
                <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
                <TabsTrigger value="leads">Hot leads</TabsTrigger>
              </TabsList>
              <TabsContent value="campaigns">
                {data.top_campaigns.length === 0 ? (
                  <EmptyState inline title="No active campaigns" />
                ) : (
                  <ul className="flex flex-col divide-y divide-[var(--border-subtle)]">
                    {data.top_campaigns.map((c) => (
                      <li key={c.id}>
                        <Link
                          href={`/portal/marketing`}
                          className="flex items-center justify-between gap-3 py-3 group"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <span className="size-2 rounded-full bg-[var(--accent-coral)] shrink-0" aria-hidden />
                            <span className="text-sm font-medium text-foreground truncate group-hover:text-[var(--brand-primary)] transition-colors">
                              {c.name}
                            </span>
                            <Badge tone="neutral" appearance="outline" size="sm" className="shrink-0">
                              {c.platform}
                            </Badge>
                          </div>
                          <span className="text-sm font-semibold tabular-nums text-[var(--text-muted)] shrink-0">
                            {formatZAR(c.budget_spent)}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </TabsContent>
              <TabsContent value="leads">
                {data.hot_leads.length === 0 ? (
                  <EmptyState inline title="No hot leads yet" />
                ) : (
                  <ul className="flex flex-col divide-y divide-[var(--border-subtle)]">
                    {data.hot_leads.map((l) => {
                      const name = [l.first_name, l.last_name].filter(Boolean).join(" ") || l.email || "Unknown";
                      return (
                        <li key={l.id}>
                          <Link
                            href={`/portal/crm`}
                            className="flex items-center justify-between gap-3 py-3 group"
                          >
                            <div className="flex items-center gap-3 min-w-0">
                              <span className="text-sm font-medium text-foreground truncate group-hover:text-[var(--brand-primary)] transition-colors">
                                {name}
                              </span>
                              <Badge tone="neutral" appearance="soft" size="sm" className="shrink-0">
                                {l.source}
                              </Badge>
                            </div>
                            <Badge
                              tone={l.score >= 70 ? "success" : "warning"}
                              appearance="soft"
                              size="sm"
                            >
                              Score {l.score}
                            </Badge>
                          </Link>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      ) : null}

      {/* Alerts */}
      {data.alerts.length > 0 ? (
        <Card variant="default" padding="lg">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Active alerts</CardTitle>
              <Badge tone="danger" appearance="soft" size="sm">
                {data.alerts.length}
              </Badge>
            </div>
          </CardHeader>
          <CardContent>
            <ul className="flex flex-col gap-2">
              {data.alerts.map((a) => {
                const { Icon, tone, label } = severityConfig(a.severity);
                return (
                  <li
                    key={a.id}
                    className="flex items-start gap-3 p-3 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]"
                  >
                    <Icon
                      className="size-4 shrink-0 mt-0.5 text-[var(--text-muted)]"
                      aria-hidden
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge tone={tone} appearance="soft" size="sm">
                          {label}
                        </Badge>
                        <span className="text-sm font-medium text-foreground">{a.message}</span>
                      </div>
                      <p className="text-xs text-[var(--text-dim)] mt-1">
                        {new Date(a.created_at).toLocaleDateString("en-ZA", {
                          day: "numeric",
                          month: "short",
                          year: "numeric",
                        })}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function ModuleMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-dim)]">
        {label}
      </span>
      <span className="text-lg font-semibold text-foreground tabular-nums truncate">
        {typeof value === "number" ? <AnimatedNumber value={value} /> : value}
      </span>
    </div>
  );
}
