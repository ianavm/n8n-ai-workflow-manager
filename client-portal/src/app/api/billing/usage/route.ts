import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// GET /api/billing/usage — current period usage vs plan limits
export async function GET() {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Get active subscription with plan limits
    const { data: subscription, error: subError } = await supabase
      .from("subscriptions")
      .select("*, plans(*)")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (subError) {
      console.error("[billing/usage] Subscription fetch error:", subError);
      return NextResponse.json(
        { error: "Failed to fetch subscription" },
        { status: 500 }
      );
    }

    if (!subscription) {
      return NextResponse.json({
        error: "No active subscription",
        usage: null,
      });
    }

    const plan = subscription.plans;
    const periodStart = subscription.current_period_start;
    const periodEnd = subscription.current_period_end;

    // Count stat events in current billing period
    const countEvents = async (eventType: string): Promise<number> => {
      const { count, error } = await supabase
        .from("stat_events")
        .select("*", { count: "exact", head: true })
        .eq("client_id", clientId)
        .eq("event_type", eventType)
        .gte("created_at", periodStart)
        .lte("created_at", periodEnd);

      if (error) {
        console.error(`[billing/usage] Count error for ${eventType}:`, error);
        return 0;
      }
      return count || 0;
    };

    // Count active workflows
    const { count: activeWorkflows } = await supabase
      .from("workflows")
      .select("*", { count: "exact", head: true })
      .eq("client_id", clientId)
      .eq("status", "active");

    const [messagesUsed, leadsUsed] = await Promise.all([
      countEvents("message_sent"),
      countEvents("lead_created"),
    ]);

    const buildMetric = (used: number, limit: number | null) => ({
      used,
      limit: limit ?? null,
      remaining: limit != null ? Math.max(0, limit - used) : null,
      percentage: limit != null && limit > 0 ? Math.round((used / limit) * 100) : null,
    });

    return NextResponse.json({
      period: {
        start: periodStart,
        end: periodEnd,
      },
      messages: buildMetric(messagesUsed, plan.limit_messages),
      leads: buildMetric(leadsUsed, plan.limit_leads),
      workflows: buildMetric(activeWorkflows || 0, plan.limit_workflows),
      agents: buildMetric(0, plan.limit_agents), // TODO: count active agents when agent tracking is built
    });
  } catch (error) {
    console.error("[billing/usage] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
