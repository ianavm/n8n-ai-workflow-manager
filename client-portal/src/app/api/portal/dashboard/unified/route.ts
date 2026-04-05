import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.profileId;
  const url = new URL(req.url);
  const period = url.searchParams.get("period") ?? "30d";
  const periodDays = period === "7d" ? 7 : period === "90d" ? 90 : 30;

  const now = new Date();
  const currentStart = new Date(now);
  currentStart.setDate(currentStart.getDate() - periodDays);
  const previousStart = new Date(currentStart);
  previousStart.setDate(previousStart.getDate() - periodDays);

  const supabase = await createServiceRoleClient();

  // Helper: safe query wrapper
  async function safe<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
    try { return await fn(); } catch { return fallback; }
  }

  const [
    profile,
    currentEvents,
    previousEvents,
    healthScore,
    mktConfigExists,
    acctConfigExists,
    activityFeed,
    uptime,
    subscription,
    alerts,
  ] = await Promise.all([
    // Profile
    safe(async () => {
      const { data } = await supabase
        .from("clients")
        .select("full_name, company_name, logo_url, brand_color, dashboard_config")
        .eq("id", clientId)
        .single();
      return data;
    }, null),

    // Current period events
    safe(async () => {
      const { data } = await supabase
        .from("stat_events")
        .select("event_type")
        .eq("client_id", clientId)
        .gte("created_at", currentStart.toISOString());
      return data ?? [];
    }, []),

    // Previous period events
    safe(async () => {
      const { data } = await supabase
        .from("stat_events")
        .select("event_type")
        .eq("client_id", clientId)
        .gte("created_at", previousStart.toISOString())
        .lt("created_at", currentStart.toISOString());
      return data ?? [];
    }, []),

    // Health score
    safe(async () => {
      const { data } = await supabase
        .from("client_health_scores")
        .select("*")
        .eq("client_id", clientId)
        .order("score_date", { ascending: false })
        .limit(1)
        .maybeSingle();
      return data;
    }, null),

    // Marketing config check
    safe(async () => {
      const { data } = await supabase
        .from("mkt_config")
        .select("id")
        .eq("client_id", clientId)
        .maybeSingle();
      return !!data;
    }, false),

    // Accounting config check
    safe(async () => {
      const { data } = await supabase
        .from("acct_config")
        .select("id")
        .eq("client_id", clientId)
        .maybeSingle();
      return !!data;
    }, false),

    // Activity feed
    safe(async () => {
      const { data } = await supabase
        .from("stat_events")
        .select("id, event_type, metadata, created_at")
        .eq("client_id", clientId)
        .order("created_at", { ascending: false })
        .limit(20);
      return data ?? [];
    }, []),

    // Uptime
    safe(async () => {
      const { data } = await supabase.rpc("get_uptime_stats", {
        p_client_id: clientId,
        p_start_date: currentStart.toISOString().split("T")[0],
        p_end_date: now.toISOString().split("T")[0],
      });
      return data as { total: number; successful: number; failed: number } | null;
    }, null),

    // Subscription
    safe(async () => {
      const { data } = await supabase.rpc("get_client_subscription", {
        client_id: clientId,
      });
      return data as { plan_name?: string; status?: string } | null;
    }, null),

    // Alerts
    safe(async () => {
      const { data } = await supabase
        .from("health_alerts")
        .select("id, alert_type, severity, message, created_at")
        .eq("client_id", clientId)
        .is("resolved_at", null)
        .order("created_at", { ascending: false })
        .limit(10);
      return data ?? [];
    }, []),
  ]);

  // Count events by type
  function countType(events: { event_type: string }[], type: string): number {
    return events.filter((e) => e.event_type === type).length;
  }

  function changePct(current: number, previous: number): number {
    if (previous === 0) return current > 0 ? 100 : 0;
    return Math.round(((current - previous) / previous) * 100);
  }

  const curLeads = countType(currentEvents, "lead_created");
  const prevLeads = countType(previousEvents, "lead_created");
  const curMsgSent = countType(currentEvents, "message_sent");
  const prevMsgSent = countType(previousEvents, "message_sent");
  const curCrashes = countType(currentEvents, "workflow_crash");
  const successRate = uptime && uptime.total > 0
    ? Math.round((uptime.successful / uptime.total) * 1000) / 10
    : 100;

  // Module KPIs (conditional)
  let mktKpis: Record<string, unknown> | null = null;
  let acctKpis: Record<string, unknown> | null = null;
  let topCampaigns: unknown[] = [];
  let hotLeads: unknown[] = [];

  if (mktConfigExists) {
    [mktKpis, topCampaigns, hotLeads] = await Promise.all([
      safe(async () => {
        const { data } = await supabase.rpc("mkt_get_dashboard_kpis", { p_client_id: clientId });
        return data as Record<string, unknown> | null;
      }, null),
      safe(async () => {
        const { data } = await supabase
          .from("mkt_campaigns")
          .select("id, name, platform, budget_spent, status")
          .eq("client_id", clientId)
          .in("status", ["active", "paused"])
          .order("budget_spent", { ascending: false })
          .limit(5);
        return data ?? [];
      }, []),
      safe(async () => {
        const { data } = await supabase
          .from("mkt_leads")
          .select("id, first_name, last_name, email, source, score, created_at")
          .eq("client_id", clientId)
          .gte("score", 70)
          .order("created_at", { ascending: false })
          .limit(5);
        return data ?? [];
      }, []),
    ]);
  }

  if (acctConfigExists) {
    acctKpis = await safe(async () => {
      const { data } = await supabase.rpc("acct_get_dashboard_kpis", { p_client_id: clientId });
      return data as Record<string, unknown> | null;
    }, null);
  }

  const totalRevenue = (acctKpis?.cash_received_month as number) ?? 0;
  const adSpend = (mktKpis?.total_spend_month as number) ?? 0;
  const activeCampaigns = (mktKpis?.active_campaigns as number) ?? 0;

  // Build sparkline placeholders (7 data points)
  function buildSparkline(value: number): number[] {
    const base = Math.max(value * 0.6, 1);
    return Array.from({ length: 7 }, (_, i) =>
      Math.round(base + (value - base) * (i / 6) + (Math.random() - 0.5) * base * 0.3)
    );
  }

  const feed = activityFeed.map((e: { id: string; event_type: string; metadata: unknown; created_at: string }) => {
    const typeMessages: Record<string, string> = {
      lead_created: "New lead captured",
      message_sent: "Message sent",
      message_received: "Message received",
      workflow_crash: "Workflow error detected",
    };
    return {
      id: e.id,
      type: e.event_type,
      message: typeMessages[e.event_type] ?? e.event_type,
      created_at: e.created_at,
      metadata: e.metadata,
    };
  });

  return NextResponse.json({
    profile: profile ?? { full_name: "User", company_name: null, logo_url: null, brand_color: "#6C63FF", dashboard_config: {} },
    kpis: {
      total_revenue: { value: totalRevenue, change_pct: 0, sparkline: buildSparkline(totalRevenue / 100) },
      new_leads: { value: curLeads, change_pct: changePct(curLeads, prevLeads), sparkline: buildSparkline(curLeads) },
      ad_spend: { value: adSpend, change_pct: 0, sparkline: buildSparkline(adSpend / 100) },
      active_campaigns: { value: activeCampaigns, change_pct: 0, sparkline: buildSparkline(activeCampaigns) },
      messages_sent: { value: curMsgSent, change_pct: changePct(curMsgSent, prevMsgSent), sparkline: buildSparkline(curMsgSent) },
      success_rate: { value: successRate, change_pct: 0, sparkline: buildSparkline(successRate) },
    },
    health: healthScore
      ? {
          composite_score: healthScore.composite_score,
          usage_score: healthScore.usage_score,
          payment_score: healthScore.payment_score,
          engagement_score: healthScore.engagement_score,
          support_score: healthScore.support_score,
          risk_level: healthScore.risk_level,
          trend: healthScore.trend ?? "stable",
        }
      : null,
    modules: { marketing: mktConfigExists, accounting: acctConfigExists },
    module_summaries: {
      ...(mktKpis ? {
        marketing: {
          active_campaigns: mktKpis.active_campaigns ?? 0,
          spend_today: (mktKpis.total_spend_month as number) ?? 0,
          leads_today: (mktKpis.leads_generated_today as number) ?? 0,
        },
      } : {}),
      ...(acctKpis ? {
        accounting: {
          receivables: (acctKpis.total_receivables as number) ?? 0,
          payables: (acctKpis.total_payables as number) ?? 0,
          overdue_count: (acctKpis.overdue_invoices as number) ?? 0,
        },
      } : {}),
    },
    activity_feed: feed,
    top_campaigns: topCampaigns,
    hot_leads: hotLeads,
    alerts,
    subscription: subscription ? { plan_name: (subscription as Record<string, unknown>).plan_name ?? "Free", status: (subscription as Record<string, unknown>).status ?? "active", trial_end: (subscription as Record<string, unknown>).trial_end ?? null } : null,
  });
}
