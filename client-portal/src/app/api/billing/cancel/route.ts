import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// POST /api/billing/cancel — cancel subscription at period end
export async function POST() {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Find active subscription
    const { data: subscription, error: fetchError } = await supabase
      .from("subscriptions")
      .select("*")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (fetchError) {
      console.error("[billing/cancel] Fetch error:", fetchError);
      return NextResponse.json(
        { error: "Failed to fetch subscription" },
        { status: 500 }
      );
    }

    if (!subscription) {
      return NextResponse.json(
        { error: "No active subscription found" },
        { status: 404 }
      );
    }

    // Set cancel at period end
    const { data: updated, error: updateError } = await supabase
      .from("subscriptions")
      .update({
        cancel_at_period_end: true,
        updated_at: new Date().toISOString(),
      })
      .eq("id", subscription.id)
      .select()
      .single();

    if (updateError) {
      console.error("[billing/cancel] Update error:", updateError);
      return NextResponse.json(
        { error: "Failed to cancel subscription" },
        { status: 500 }
      );
    }

    // If subscription has a PayFast token, attempt to cancel recurring billing
    if (subscription.payfast_token) {
      try {
        const isSandbox = process.env.PAYFAST_SANDBOX === "true";
        const cancelUrl = isSandbox
          ? `https://sandbox.payfast.co.za/eng/recurring/update/${subscription.payfast_token}`
          : `https://www.payfast.co.za/eng/recurring/update/${subscription.payfast_token}`;

        await fetch(cancelUrl, {
          method: "PUT",
          headers: {
            "Content-Type": "application/json",
            "merchant-id": process.env.PAYFAST_MERCHANT_ID!,
            version: "v1",
            timestamp: new Date().toISOString(),
          },
          body: JSON.stringify({ status: "PAUSED" }),
        });
      } catch (pfError) {
        // Log but don't fail the request - subscription is marked for cancellation
        console.error("[billing/cancel] PayFast cancel error:", pfError);
      }
    }

    // Log activity
    await supabase.from("activity_log").insert({
      actor_type: "client",
      actor_id: clientId,
      action: "subscription_cancel_requested",
      target_type: "subscription",
      target_id: subscription.id,
      details: {
        cancel_at_period_end: true,
        current_period_end: subscription.current_period_end,
      },
    });

    return NextResponse.json({
      subscription: updated,
      message: "Subscription will be cancelled at the end of the current billing period.",
    });
  } catch (error) {
    console.error("[billing/cancel] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
