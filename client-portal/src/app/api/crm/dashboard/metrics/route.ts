import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

const querySchema = z.object({
  client: z.string().uuid().optional(),
  range: z
    .enum(["7d", "30d", "90d"])
    .default("30d"),
});

const RANGE_DAYS: Record<"7d" | "30d" | "90d", number> = { "7d": 7, "30d": 30, "90d": 90 };

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const parsed = querySchema.safeParse(Object.fromEntries(url.searchParams));
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid query" }, { status: 400 });
  }
  const { client, range } = parsed.data;

  const ctx = await getCrmViewerContext(client);
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass client" },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();
  const days = RANGE_DAYS[range];
  const since = new Date(Date.now() - days * 24 * 60 * 60 * 1000).toISOString();

  const [
    { count: totalLeads },
    { count: wonCount },
    { count: lostCount },
    { data: openDeals },
    { data: dailyRows },
    { data: stages },
    { data: stageRows },
  ] = await Promise.all([
    supabase.from("crm_leads").select("id", { count: "exact", head: true }).eq("client_id", clientId),
    supabase
      .from("crm_leads")
      .select("id", { count: "exact", head: true })
      .eq("client_id", clientId)
      .eq("stage_key", "closed_won"),
    supabase
      .from("crm_leads")
      .select("id", { count: "exact", head: true })
      .eq("client_id", clientId)
      .eq("stage_key", "closed_lost"),
    supabase
      .from("crm_leads")
      .select("deal_value_zar")
      .eq("client_id", clientId)
      .not("stage_key", "in", "(closed_won,closed_lost)"),
    supabase
      .from("crm_leads")
      .select("created_at")
      .eq("client_id", clientId)
      .gte("created_at", since),
    supabase
      .from("crm_stages")
      .select("key, label, color, order_index")
      .eq("client_id", clientId)
      .order("order_index"),
    supabase.from("crm_leads").select("stage_key").eq("client_id", clientId),
  ]);

  const totalPipeline = (openDeals ?? []).reduce((acc, r) => acc + Number(r.deal_value_zar ?? 0), 0);
  const decided = (wonCount ?? 0) + (lostCount ?? 0);
  const winRate = decided > 0 ? ((wonCount ?? 0) / decided) * 100 : null;

  const dayMap = new Map<string, number>();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setUTCDate(d.getUTCDate() - i);
    dayMap.set(d.toISOString().slice(0, 10), 0);
  }
  for (const r of dailyRows ?? []) {
    const k = (r.created_at as string).slice(0, 10);
    if (dayMap.has(k)) dayMap.set(k, (dayMap.get(k) ?? 0) + 1);
  }

  const stageCounts = new Map<string, number>();
  for (const r of stageRows ?? []) stageCounts.set(r.stage_key, (stageCounts.get(r.stage_key) ?? 0) + 1);

  return NextResponse.json({
    success: true,
    data: {
      totalLeads: totalLeads ?? 0,
      totalPipeline,
      closedWon: wonCount ?? 0,
      closedLost: lostCount ?? 0,
      winRate,
      dailyCreated: Array.from(dayMap.entries()).map(([day, count]) => ({ day, count })),
      byStage: (stages ?? []).map((s) => ({
        stage_key: s.key,
        label: s.label,
        color: s.color ?? null,
        count: stageCounts.get(s.key) ?? 0,
      })),
      range,
    },
  });
}
