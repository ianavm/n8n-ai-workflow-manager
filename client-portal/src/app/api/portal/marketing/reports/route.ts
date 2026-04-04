import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

type ReportType = "overview" | "campaign" | "platform" | "attribution";

interface PerformanceRow {
  date: string;
  platform: string;
  campaign_id: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  leads_generated: number;
}

interface CampaignRef {
  id: string;
  name: string;
}

interface DailyMetrics {
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  leads_generated: number;
}

interface PlatformBreakdown {
  platform: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
}

interface TopCampaign {
  campaign_id: string;
  name: string;
  spend: number;
}

interface PlatformSeries {
  platform: string;
  daily: DailyMetrics[];
  totals: DailyMetrics;
}

function aggregateByDate(rows: PerformanceRow[]): DailyMetrics[] {
  const map = new Map<string, DailyMetrics>();

  for (const row of rows) {
    const existing = map.get(row.date);
    if (existing) {
      map.set(row.date, {
        date: row.date,
        impressions: existing.impressions + (row.impressions ?? 0),
        clicks: existing.clicks + (row.clicks ?? 0),
        spend: existing.spend + (row.spend ?? 0),
        conversions: existing.conversions + (row.conversions ?? 0),
        leads_generated: existing.leads_generated + (row.leads_generated ?? 0),
      });
    } else {
      map.set(row.date, {
        date: row.date,
        impressions: row.impressions ?? 0,
        clicks: row.clicks ?? 0,
        spend: row.spend ?? 0,
        conversions: row.conversions ?? 0,
        leads_generated: row.leads_generated ?? 0,
      });
    }
  }

  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

function sumTotals(rows: DailyMetrics[]): DailyMetrics {
  return rows.reduce(
    (acc, row) => ({
      date: "",
      impressions: acc.impressions + row.impressions,
      clicks: acc.clicks + row.clicks,
      spend: acc.spend + row.spend,
      conversions: acc.conversions + row.conversions,
      leads_generated: acc.leads_generated + row.leads_generated,
    }),
    { date: "", impressions: 0, clicks: 0, spend: 0, conversions: 0, leads_generated: 0 }
  );
}

function aggregateByPlatform(rows: PerformanceRow[]): PlatformBreakdown[] {
  const map = new Map<string, PlatformBreakdown>();

  for (const row of rows) {
    const existing = map.get(row.platform);
    if (existing) {
      map.set(row.platform, {
        platform: row.platform,
        impressions: existing.impressions + (row.impressions ?? 0),
        clicks: existing.clicks + (row.clicks ?? 0),
        spend: existing.spend + (row.spend ?? 0),
        conversions: existing.conversions + (row.conversions ?? 0),
      });
    } else {
      map.set(row.platform, {
        platform: row.platform,
        impressions: row.impressions ?? 0,
        clicks: row.clicks ?? 0,
        spend: row.spend ?? 0,
        conversions: row.conversions ?? 0,
      });
    }
  }

  return Array.from(map.values()).sort((a, b) => b.spend - a.spend);
}

function topCampaignsBySpend(
  rows: PerformanceRow[],
  campaignNames: Map<string, string>,
  limit: number
): TopCampaign[] {
  const map = new Map<string, number>();

  for (const row of rows) {
    if (!row.campaign_id) continue;
    map.set(row.campaign_id, (map.get(row.campaign_id) ?? 0) + (row.spend ?? 0));
  }

  return Array.from(map.entries())
    .map(([campaign_id, spend]) => ({
      campaign_id,
      name: campaignNames.get(campaign_id) ?? campaign_id,
      spend,
    }))
    .sort((a, b) => b.spend - a.spend)
    .slice(0, limit);
}

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const url = new URL(req.url);
  const startDate = url.searchParams.get("start_date");
  const endDate = url.searchParams.get("end_date");
  const reportType = (url.searchParams.get("report_type") ?? "overview") as ReportType;
  const campaignId = url.searchParams.get("campaign_id");

  if (!startDate || !endDate) {
    return NextResponse.json(
      { error: "start_date and end_date are required (YYYY-MM-DD)" },
      { status: 400 }
    );
  }

  if (!["overview", "campaign", "platform", "attribution"].includes(reportType)) {
    return NextResponse.json(
      { error: "report_type must be overview, campaign, platform, or attribution" },
      { status: 400 }
    );
  }

  if (reportType === "campaign" && !campaignId) {
    return NextResponse.json(
      { error: "campaign_id is required for campaign report type" },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Build base query
  let query = supabase
    .from("mkt_performance")
    .select("*")
    .eq("client_id", clientId)
    .gte("date", startDate)
    .lte("date", endDate)
    .order("date", { ascending: true });

  if (campaignId) {
    query = query.eq("campaign_id", campaignId);
  }

  const { data: rows, error } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const perfRows = (rows ?? []) as PerformanceRow[];

  // Fetch campaign names for top-campaigns breakdown
  const campaignIds = [...new Set(perfRows.map((r) => r.campaign_id).filter(Boolean))];
  const campaignNames = new Map<string, string>();

  if (campaignIds.length > 0) {
    const { data: campaigns } = await supabase
      .from("mkt_campaigns")
      .select("id, name")
      .in("id", campaignIds);

    for (const c of (campaigns ?? []) as CampaignRef[]) {
      campaignNames.set(c.id, c.name);
    }
  }

  // Build response based on report type
  if (reportType === "campaign") {
    const timeSeries = aggregateByDate(perfRows);
    const totals = sumTotals(timeSeries);

    return NextResponse.json({
      report_type: reportType,
      date_range: { start_date: startDate, end_date: endDate },
      time_series: timeSeries,
      totals,
      campaign_name: campaignNames.get(campaignId!) ?? campaignId,
    });
  }

  if (reportType === "platform") {
    const platformMap = new Map<string, PerformanceRow[]>();
    for (const row of perfRows) {
      const list = platformMap.get(row.platform) ?? [];
      list.push(row);
      platformMap.set(row.platform, list);
    }

    const platforms: PlatformSeries[] = Array.from(platformMap.entries()).map(
      ([platform, pRows]) => {
        const daily = aggregateByDate(pRows);
        const totals = sumTotals(daily);
        return { platform, daily, totals };
      }
    );

    return NextResponse.json({
      report_type: reportType,
      date_range: { start_date: startDate, end_date: endDate },
      platforms,
    });
  }

  // Default: overview (also handles attribution for now)
  const timeSeries = aggregateByDate(perfRows);
  const totals = sumTotals(timeSeries);
  const platformBreakdown = aggregateByPlatform(perfRows);
  const topCampaigns = topCampaignsBySpend(perfRows, campaignNames, 5);

  return NextResponse.json({
    report_type: reportType,
    date_range: { start_date: startDate, end_date: endDate },
    time_series: timeSeries,
    totals,
    platform_breakdown: platformBreakdown,
    top_campaigns: topCampaigns,
  });
}
