"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  DollarSign,
  Percent,
  Target,
  TrendingUp,
  Users,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { KPIGrid } from "@/components/portal/KPIGrid";
import { StatCard } from "@/components/portal/StatCard";
import { EmptyState } from "@/components/portal/EmptyState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import { CampaignStatusBadge } from "@/components/marketing/CampaignStatusBadge";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";

interface DashboardKPIs {
  total_spend_month: number;
  leads_generated_month: number;
  leads_generated_today: number;
  active_campaigns: number;
  avg_cpl: number;
  avg_cpa: number;
  total_roas: number;
  conversion_rate: number;
  scheduled_posts: number;
  pipeline_value: number;
  open_tasks: number;
  unread_conversations: number;
}

interface Campaign {
  id: string;
  name: string;
  platform: string;
  status: string;
  budget_spent: number;
  budget_total: number;
}

interface Lead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  source: string;
  stage: string;
  created_at: string;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export default function MarketingDashboard() {
  const supabase = createClient();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [kpiRes, campRes, leadRes] = await Promise.all([
        fetch("/api/portal/marketing/dashboard"),
        supabase
          .from("mkt_campaigns")
          .select("id, name, platform, status, budget_spent, budget_total")
          .in("status", ["active", "paused"])
          .order("budget_spent", { ascending: false })
          .limit(5),
        supabase
          .from("mkt_leads")
          .select("id, first_name, last_name, email, source, stage, created_at")
          .order("created_at", { ascending: false })
          .limit(5),
      ]);

      if (kpiRes.ok) setKpis(await kpiRes.json());
      if (campRes.data) setCampaigns(campRes.data);
      if (leadRes.data) setLeads(leadRes.data);
      setLoading(false);
    }
    load();
  }, [supabase]);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Marketing"
        title="Marketing dashboard"
        description="Campaign performance, leads, and content at a glance."
      />

      <KPIGrid cols={6}>
        <StatCard
          label="Ad spend (month)"
          value={kpis ? kpis.total_spend_month / 100 : 0}
          prefix="R"
          icon={<DollarSign className="size-4" />}
          accent="coral"
          loading={loading}
        />
        <StatCard
          label="Leads generated"
          value={kpis?.leads_generated_month ?? 0}
          icon={<Users className="size-4" />}
          accent="teal"
          loading={loading}
        />
        <StatCard
          label="Avg CPL"
          value={kpis ? kpis.avg_cpl / 100 : 0}
          prefix="R"
          icon={<Target className="size-4" />}
          accent="purple"
          loading={loading}
        />
        <StatCard
          label="Active campaigns"
          value={kpis?.active_campaigns ?? 0}
          icon={<BarChart3 className="size-4" />}
          accent="warning"
          loading={loading}
        />
        <StatCard
          label="ROAS"
          value={kpis?.total_roas ?? 0}
          suffix="x"
          decimals={1}
          icon={<TrendingUp className="size-4" />}
          accent="teal"
          loading={loading}
        />
        <StatCard
          label="Conv. rate"
          value={kpis?.conversion_rate ?? 0}
          suffix="%"
          decimals={1}
          icon={<Percent className="size-4" />}
          accent="purple"
          loading={loading}
        />
      </KPIGrid>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Top campaigns</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {campaigns.length === 0 && !loading ? (
              <EmptyState inline title="No active campaigns yet" />
            ) : (
              <ul className="flex flex-col gap-2">
                {campaigns.map((c) => (
                  <li
                    key={c.id}
                    className="flex items-center justify-between gap-3 p-3 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)]"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <PlatformIcon platform={c.platform} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-foreground truncate">{c.name}</p>
                        <p className="text-xs text-[var(--text-dim)] mt-0.5 truncate">
                          {formatZAR(c.budget_spent)} of {formatZAR(c.budget_total)}
                        </p>
                      </div>
                    </div>
                    <CampaignStatusBadge status={c.status} />
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Recent leads</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {leads.length === 0 && !loading ? (
              <EmptyState inline title="No leads captured yet" />
            ) : (
              <ul className="flex flex-col gap-2">
                {leads.map((l) => (
                  <li
                    key={l.id}
                    className="flex items-center justify-between gap-3 p-3 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)]"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground truncate">
                        {[l.first_name, l.last_name].filter(Boolean).join(" ") || l.email || "Unknown"}
                      </p>
                      <p className="text-xs text-[var(--text-dim)] mt-0.5 capitalize">
                        {l.source.replace("_", " ")} · {l.stage}
                      </p>
                    </div>
                    <span className="text-xs text-[var(--text-dim)] shrink-0">
                      {new Date(l.created_at).toLocaleDateString("en-ZA")}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
