import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// GET /api/billing/subscription — return current subscription + plan + usage
export async function GET() {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Get subscription with plan details
    const { data: subscription, error: subError } = await supabase
      .from("subscriptions")
      .select("*, plans(*)")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing", "past_due"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (subError) {
      console.error("[billing/subscription] Subscription fetch error:", subError);
      return NextResponse.json(
        { error: "Failed to fetch subscription" },
        { status: 500 }
      );
    }

    if (!subscription) {
      return NextResponse.json({ subscription: null, usage: null });
    }

    // Get current period usage
    const { data: usage, error: usageError } = await supabase.rpc(
      "get_client_usage",
      { p_client_id: clientId }
    );

    if (usageError) {
      console.error("[billing/subscription] Usage fetch error:", usageError);
    }

    return NextResponse.json({
      subscription: {
        id: subscription.id,
        status: subscription.status,
        billing_interval: subscription.billing_interval,
        current_period_start: subscription.current_period_start,
        current_period_end: subscription.current_period_end,
        cancel_at_period_end: subscription.cancel_at_period_end,
        payfast_token: subscription.payfast_token,
        created_at: subscription.created_at,
        plan: subscription.plans,
      },
      usage: usage ?? null,
    });
  } catch (error) {
    console.error("[billing/subscription] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
