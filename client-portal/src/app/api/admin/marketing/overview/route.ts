import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface ClientRow {
  client_id: string;
  client_name: string;
  total_spend: number;
  leads: number;
  cpl: number;
  active_campaigns: number;
  budget_monthly_cap: number;
  budget_usage_pct: number;
  has_config: boolean;
}

interface Alert {
  type: "budget_warning" | "failed_posts" | "stale_leads";
  client_name: string;
  client_id: string;
  message: string;
}

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }
  if (session.role === "superior_admin") {
    return NextResponse.json(
      { error: "POPIA: superior admin cannot view client business data" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();
  const url = new URL(req.url);
  const singleClientKpis = url.searchParams.get("client_kpis");

  /* ── Single-client KPI mode (for client detail page) ── */
  if (singleClientKpis) {
    const { data, error } = await supabase.rpc("mkt_get_dashboard_kpis", {
      p_client_id: singleClientKpis,
    });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ data });
  }

  /* ── Cross-client overview ── */
  const periodStart = new Date();
  periodStart.setDate(1);
  periodStart.setHours(0, 0, 0, 0);
  const periodStartStr = periodStart.toISOString().split("T")[0];

  try {
    /* Fetch configs with client names */
    const { data: configs, error: cfgErr } = await supabase
      .from("mkt_config")
      .select("client_id, budget_monthly_cap, clients(full_name)");

    if (cfgErr) {
      return NextResponse.json({ error: cfgErr.message }, { status: 500 });
    }

    const clientIds = (configs ?? []).map(
      (c: Record<string, unknown>) => c.client_id as string
    );

    if (clientIds.length === 0) {
      return NextResponse.json({
        data: {
          total_spend_month: 0,
          total_leads_month: 0,
          avg_cpl: 0,
          active_campaigns: 0,
          clients: [],
          alerts: [],
        },
      });
    }

    /* Fetch performance, leads, campaigns in parallel */
    const [perfResult, leadsResult, campaignsResult, failedPostsResult, staleLeadsResult] =
      await Promise.all([
        supabase
          .from("mkt_performance")
          .select("client_id, spend, leads_generated")
          .in("client_id", clientIds)
          .gte("date", periodStartStr),
        supabase
          .from("mkt_leads")
          .select("client_id")
          .in("client_id", clientIds)
          .gte("created_at", periodStart.toISOString()),
        supabase
          .from("mkt_campaigns")
          .select("client_id, status")
          .in("client_id", clientIds)
          .in("status", ["active", "draft", "paused", "pending_review", "approved"]),
        supabase
          .from("mkt_content_calendar")
          .select("client_id")
          .in("client_id", clientIds)
          .eq("status", "failed"),
        supabase
          .from("mkt_leads")
          .select("client_id, updated_at")
          .in("client_id", clientIds)
          .not("stage", "in", '("won","lost")'),
      ]);

    /* Aggregate per-client */
    const spendByClient: Record<string, number> = {};
    const leadsByPerf: Record<string, number> = {};
    for (const row of perfResult.data ?? []) {
      const cid = row.client_id as string;
      spendByClient[cid] = (spendByClient[cid] ?? 0) + (row.spend as number);
      leadsByPerf[cid] = (leadsByPerf[cid] ?? 0) + (row.leads_generated as number);
    }

    const leadsByClient: Record<string, number> = {};
    for (const row of leadsResult.data ?? []) {
      const cid = row.client_id as string;
      leadsByClient[cid] = (leadsByClient[cid] ?? 0) + 1;
    }

    const activeCampsByClient: Record<string, number> = {};
    for (const row of campaignsResult.data ?? []) {
      if (row.status === "active") {
        const cid = row.client_id as string;
        activeCampsByClient[cid] = (activeCampsByClient[cid] ?? 0) + 1;
      }
    }

    /* Build client rows */
    const clients: ClientRow[] = (configs ?? []).map(
      (cfg: Record<string, unknown>) => {
        const cid = cfg.client_id as string;
        const clientRef = cfg.clients as { full_name: string } | null;
        const spend = spendByClient[cid] ?? 0;
        const leads = leadsByClient[cid] ?? 0;
        const cap = cfg.budget_monthly_cap as number;
        return {
          client_id: cid,
          client_name: clientRef?.full_name ?? "Unknown",
          total_spend: spend,
          leads,
          cpl: leads > 0 ? Math.round(spend / leads) : 0,
          active_campaigns: activeCampsByClient[cid] ?? 0,
          budget_monthly_cap: cap,
          budget_usage_pct: cap > 0 ? (spend / cap) * 100 : 0,
          has_config: true,
        };
      }
    );

    /* Sort by spend desc */
    clients.sort((a, b) => b.total_spend - a.total_spend);

    /* Totals */
    const totalSpend = clients.reduce((s, c) => s + c.total_spend, 0);
    const totalLeads = clients.reduce((s, c) => s + c.leads, 0);
    const totalActiveCampaigns = clients.reduce(
      (s, c) => s + c.active_campaigns,
      0
    );

    /* Build alerts */
    const alerts: Alert[] = [];

    /* Budget warnings (>80%) */
    for (const c of clients) {
      if (c.budget_monthly_cap > 0 && c.budget_usage_pct >= 80) {
        alerts.push({
          type: "budget_warning",
          client_name: c.client_name,
          client_id: c.client_id,
          message: `Budget at ${Math.round(c.budget_usage_pct)}% (${formatZAR(c.total_spend)} of ${formatZAR(c.budget_monthly_cap)})`,
        });
      }
    }

    /* Failed posts */
    const failedByClient: Record<string, number> = {};
    for (const row of failedPostsResult.data ?? []) {
      const cid = row.client_id as string;
      failedByClient[cid] = (failedByClient[cid] ?? 0) + 1;
    }
    for (const c of clients) {
      const failed = failedByClient[c.client_id] ?? 0;
      if (failed > 0) {
        alerts.push({
          type: "failed_posts",
          client_name: c.client_name,
          client_id: c.client_id,
          message: `${failed} failed post${failed > 1 ? "s" : ""} in calendar`,
        });
      }
    }

    /* Stale leads (no activity in 7 days) */
    const sevenDaysAgo = new Date();
    sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);
    const staleByClient: Record<string, number> = {};
    for (const row of staleLeadsResult.data ?? []) {
      const updatedAt = new Date(row.updated_at as string);
      if (updatedAt < sevenDaysAgo) {
        const cid = row.client_id as string;
        staleByClient[cid] = (staleByClient[cid] ?? 0) + 1;
      }
    }
    for (const c of clients) {
      const stale = staleByClient[c.client_id] ?? 0;
      if (stale > 0) {
        alerts.push({
          type: "stale_leads",
          client_name: c.client_name,
          client_id: c.client_id,
          message: `${stale} lead${stale > 1 ? "s" : ""} with no activity in 7+ days`,
        });
      }
    }

    return NextResponse.json({
      data: {
        total_spend_month: totalSpend,
        total_leads_month: totalLeads,
        avg_cpl: totalLeads > 0 ? Math.round(totalSpend / totalLeads) : 0,
        active_campaigns: totalActiveCampaigns,
        clients,
        alerts,
      },
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Internal server error";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}
