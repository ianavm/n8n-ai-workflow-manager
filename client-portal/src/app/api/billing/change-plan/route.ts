import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { generatePaymentData, getPayFastUrl } from "@/lib/payfast";

export const dynamic = "force-dynamic";

// POST /api/billing/change-plan — upgrade or downgrade plan
export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await request.json();
    const { planSlug, billingInterval } = body;

    if (!planSlug || !billingInterval) {
      return NextResponse.json(
        { error: "planSlug and billingInterval are required" },
        { status: 400 }
      );
    }

    if (billingInterval !== "monthly" && billingInterval !== "yearly") {
      return NextResponse.json(
        { error: "billingInterval must be 'monthly' or 'yearly'" },
        { status: 400 }
      );
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Look up the new plan
    const { data: newPlan, error: planError } = await supabase
      .from("plans")
      .select("*")
      .eq("slug", planSlug)
      .eq("is_active", true)
      .single();

    if (planError || !newPlan) {
      return NextResponse.json(
        { error: "Plan not found" },
        { status: 404 }
      );
    }

    // Cancel current subscription immediately
    const { data: currentSub } = await supabase
      .from("subscriptions")
      .select("*")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (currentSub) {
      await supabase
        .from("subscriptions")
        .update({
          status: "canceled",
          canceled_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        })
        .eq("id", currentSub.id);

      // Cancel PayFast recurring if token exists
      if (currentSub.payfast_token) {
        try {
          const isSandbox = process.env.PAYFAST_SANDBOX === "true";
          const cancelUrl = isSandbox
            ? `https://sandbox.payfast.co.za/eng/recurring/update/${currentSub.payfast_token}`
            : `https://www.payfast.co.za/eng/recurring/update/${currentSub.payfast_token}`;

          await fetch(cancelUrl, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              "merchant-id": process.env.PAYFAST_MERCHANT_ID!,
              version: "v1",
              timestamp: new Date().toISOString(),
            },
            body: JSON.stringify({ status: "CANCELLED" }),
          });
        } catch (pfError) {
          console.error("[billing/change-plan] PayFast cancel error:", pfError);
        }
      }

      // Log cancellation
      await supabase.from("activity_log").insert({
        actor_type: "client",
        actor_id: clientId,
        action: "subscription_canceled_for_plan_change",
        target_type: "subscription",
        target_id: currentSub.id,
        details: { old_plan_id: currentSub.plan_id, new_plan_slug: planSlug },
      });
    }

    // Get client details for new checkout
    const { data: client, error: clientError } = await supabase
      .from("clients")
      .select("id, email, full_name")
      .eq("id", clientId)
      .single();

    if (clientError || !client) {
      return NextResponse.json(
        { error: "Client not found" },
        { status: 404 }
      );
    }

    // Generate new payment data
    const amount =
      billingInterval === "monthly"
        ? newPlan.price_monthly
        : newPlan.price_yearly;

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

    const paymentData = generatePaymentData({
      clientId: client.id,
      clientEmail: client.email,
      clientName: client.full_name,
      planName: newPlan.name,
      amount,
      billingInterval,
      returnUrl: `${baseUrl}/billing?status=success&changed=true`,
      cancelUrl: `${baseUrl}/billing?status=cancelled`,
      notifyUrl: `${baseUrl}/api/webhooks/payfast`,
    });

    const paymentDataWithCustom: Record<string, string> = {
      ...paymentData,
      custom_str1: client.id,
      custom_str2: newPlan.id,
    };

    return NextResponse.json({
      paymentUrl: getPayFastUrl(),
      paymentData: paymentDataWithCustom,
    });
  } catch (error) {
    console.error("[billing/change-plan] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
