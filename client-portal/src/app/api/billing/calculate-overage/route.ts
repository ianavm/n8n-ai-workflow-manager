import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// Overage rates (in cents per unit)
const OVERAGE_RATES = {
  messages: 50, // R0.50 per message
  leads: 200, // R2.00 per lead
};

// POST /api/billing/calculate-overage — calculate end-of-period overages
// Called by n8n workflow or admin action
export async function POST(request: NextRequest) {
  try {
    const session = await getSession();

    // Allow admin access or API key for n8n automation
    const apiKey = request.headers.get("x-api-key");
    if (apiKey && !process.env.INTERNAL_API_KEY) {
      return NextResponse.json({ error: "API key not configured" }, { status: 401 });
    }
    const isApiAuth = !!process.env.INTERNAL_API_KEY && apiKey === process.env.INTERNAL_API_KEY;

    if (!isApiAuth && (!session || session.role !== "superior_admin")) {
      return NextResponse.json({ error: "Superior admin or API key required" }, { status: 403 });
    }

    const body = await request.json();
    const { clientId, periodStart } = body;

    // If no clientId, process all clients for the period
    const supabase = await createServiceRoleClient();

    const now = new Date();
    const targetPeriodStart = periodStart
      || new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];

    // Get usage records for the period
    let query = supabase
      .from("usage_records")
      .select("*")
      .eq("period_start", targetPeriodStart);

    if (clientId) {
      query = query.eq("client_id", clientId);
    }

    const { data: usageRecords, error: usageError } = await query;

    if (usageError) {
      console.error("[billing/calculate-overage] Usage fetch error:", usageError);
      return NextResponse.json({ error: "Failed to fetch usage records" }, { status: 500 });
    }

    const results: Array<{
      clientId: string;
      overageMessages: number;
      overageLeads: number;
      totalOverageCents: number;
    }> = [];

    for (const record of usageRecords ?? []) {
      // Get client's merged limits
      const { data: mergedLimits } = await supabase.rpc("get_client_merged_limits", {
        p_client_id: record.client_id,
      });

      if (!mergedLimits) continue;

      const msgLimit = (mergedLimits as Record<string, number>).messages ?? 0;
      const leadLimit = (mergedLimits as Record<string, number>).leads ?? 0;

      // Calculate overages (skip unlimited = -1)
      const overageMessages = msgLimit !== -1
        ? Math.max(0, record.messages_used - msgLimit)
        : 0;
      const overageLeads = leadLimit !== -1
        ? Math.max(0, record.leads_used - leadLimit)
        : 0;

      const totalOverageCents =
        overageMessages * OVERAGE_RATES.messages +
        overageLeads * OVERAGE_RATES.leads;

      if (totalOverageCents > 0) {
        // Update usage record with overage data
        await supabase
          .from("usage_records")
          .update({
            overage_messages: overageMessages,
            overage_leads: overageLeads,
            overage_amount_cents: totalOverageCents,
            updated_at: new Date().toISOString(),
          })
          .eq("id", record.id);

        results.push({
          clientId: record.client_id,
          overageMessages,
          overageLeads,
          totalOverageCents,
        });
      }
    }

    return NextResponse.json({
      period: targetPeriodStart,
      processedRecords: usageRecords?.length ?? 0,
      clientsWithOverage: results.length,
      results,
      totalOverageRevenue: results.reduce((sum, r) => sum + r.totalOverageCents, 0),
    });
  } catch (error) {
    console.error("[billing/calculate-overage] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
