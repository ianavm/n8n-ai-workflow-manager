import { redirect } from "next/navigation";
import { Target } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { KPIStatCard } from "@/components/crm/KPIStatCard";
import { CardShell } from "@/components/crm/CardShell";
import { EmptyState } from "@/components/crm/EmptyState";
import { DashboardCharts } from "@/components/crm/DashboardCharts";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import type { CrmLead } from "@/lib/crm/types";

export const dynamic = "force-dynamic";

interface DashboardMetrics {
  totalLeads: number;
  totalPipeline: number;
  closedWon: number;
  winRate: number | null;
  byIndustry: Array<{ industry: string; count: number }>;
  byStage: Array<{ stage_key: string; label: string; color: string | null; count: number }>;
  dailyCreated: Array<{ day: string; count: number }>;
}

async function loadMetrics(clientId: string): Promise<DashboardMetrics> {
  const supabase = await createServerSupabaseClient();

  const [
    { count: totalLeads },
    { data: pipelineRows },
    { data: wonRows },
    { data: industryRows },
    { data: stageRows },
    { data: dailyRows },
    { data: stages },
  ] = await Promise.all([
    supabase
      .from("crm_leads")
      .select("id", { count: "exact", head: true })
      .eq("client_id", clientId),
    supabase
      .from("crm_leads")
      .select("deal_value_zar, stage_key")
      .eq("client_id", clientId)
      .not("stage_key", "in", "(closed_won,closed_lost)"),
    supabase
      .from("crm_leads")
      .select("id, deal_value_zar")
      .eq("client_id", clientId)
      .eq("stage_key", "closed_won"),
    supabase
      .from("crm_leads")
      .select("company_id, crm_companies!inner(industry)")
      .eq("client_id", clientId)
      .limit(1000),
    supabase
      .from("crm_leads")
      .select("stage_key")
      .eq("client_id", clientId),
    supabase
      .from("crm_leads")
      .select("created_at")
      .eq("client_id", clientId)
      .gte("created_at", new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString()),
    supabase
      .from("crm_stages")
      .select("key, label, order_index, color")
      .eq("client_id", clientId)
      .order("order_index"),
  ]);

  const totalPipeline = (pipelineRows ?? []).reduce(
    (acc, r) => acc + Number(r.deal_value_zar ?? 0),
    0,
  );
  const closedLostCount = await supabase
    .from("crm_leads")
    .select("id", { count: "exact", head: true })
    .eq("client_id", clientId)
    .eq("stage_key", "closed_lost");
  const wonCount = (wonRows ?? []).length;
  const decided = wonCount + (closedLostCount.count ?? 0);
  const winRate = decided > 0 ? (wonCount / decided) * 100 : null;

  // Industry donut
  const industryMap = new Map<string, number>();
  for (const row of industryRows ?? []) {
    const rel = row as unknown as { crm_companies: { industry: string | null } | null };
    const ind = rel.crm_companies?.industry ?? "Unknown";
    industryMap.set(ind, (industryMap.get(ind) ?? 0) + 1);
  }
  const byIndustry = Array.from(industryMap.entries())
    .map(([industry, count]) => ({ industry, count }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 6);

  // Stage bars
  const stageCounts = new Map<string, number>();
  for (const r of stageRows ?? []) stageCounts.set(r.stage_key, (stageCounts.get(r.stage_key) ?? 0) + 1);
  const byStage = (stages ?? []).map((s) => ({
    stage_key: s.key,
    label: s.label,
    color: s.color ?? null,
    count: stageCounts.get(s.key) ?? 0,
  }));

  // Daily line (30-day)
  const dayMap = new Map<string, number>();
  for (let i = 29; i >= 0; i--) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - i);
    const k = d.toISOString().slice(0, 10);
    dayMap.set(k, 0);
  }
  for (const r of dailyRows ?? []) {
    const k = (r.created_at as string).slice(0, 10);
    if (dayMap.has(k)) dayMap.set(k, (dayMap.get(k) ?? 0) + 1);
  }
  const dailyCreated = Array.from(dayMap.entries()).map(([day, count]) => ({ day, count }));

  return {
    totalLeads: totalLeads ?? 0,
    totalPipeline,
    closedWon: wonCount,
    winRate,
    byIndustry,
    byStage,
    dailyCreated,
  };
}

function formatZar(amount: number): string {
  if (amount >= 1_000_000) return `R ${(amount / 1_000_000).toFixed(1)}M`;
  if (amount >= 1_000) return `R ${(amount / 1_000).toFixed(1)}k`;
  return `R ${amount.toFixed(0)}`;
}

export default async function CrmDashboardPage() {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");

  const clientId = resolveScopedClientId(ctx);

  if (!clientId) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="CRM Dashboard"
          description="You're signed in as an AVM operator. Pick a client org to view their pipeline."
        />
        <EmptyState
          icon={Target}
          title="Select a client"
          description="As an AVM admin, the CRM is scoped per client. Pass ?client=<uuid> in the URL (client switcher UI coming soon)."
        />
      </div>
    );
  }

  const metrics = await loadMetrics(clientId);
  const hasData = metrics.totalLeads > 0;

  return (
    <div className="space-y-6">
      <PageHeader
        title="CRM Dashboard"
        description="Live view of your pipeline — scraping, research, outreach, and outcomes, all in one place."
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <KPIStatCard
          label="Total Pipeline"
          value={formatZar(metrics.totalPipeline)}
          hint="Open deals excluding closed won/lost"
        />
        <KPIStatCard
          label="Closed Won"
          value={metrics.closedWon}
          tone="positive"
          hint="All-time"
        />
        <KPIStatCard label="Total Leads" value={metrics.totalLeads} />
        <KPIStatCard
          label="Win Rate"
          value={metrics.winRate === null ? "—" : `${metrics.winRate.toFixed(0)}%`}
          hint={metrics.winRate === null ? "No decided deals yet" : "Won ÷ (Won + Lost)"}
        />
      </div>

      {hasData ? (
        <DashboardCharts
          dailyCreated={metrics.dailyCreated}
          byIndustry={metrics.byIndustry}
          byStage={metrics.byStage}
          winRate={metrics.winRate}
        />
      ) : (
        <CardShell>
          <EmptyState
            icon={Target}
            title="No leads yet"
            description="Once your AVM team runs the scraper (or you import a CSV), leads will start appearing here. First results typically land within 24 hours."
          />
        </CardShell>
      )}
    </div>
  );
}

export type { CrmLead };
