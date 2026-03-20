import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { createCheckoutSession } from "@/lib/stripe";

export const dynamic = "force-dynamic";

// POST /api/billing/checkout-stripe — create Stripe Checkout session (USD/EUR/GBP)
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

    // Look up plan
    const { data: plan, error: planError } = await supabase
      .from("plans")
      .select("*")
      .eq("slug", planSlug)
      .eq("is_active", true)
      .single();

    if (planError || !plan) {
      return NextResponse.json({ error: "Plan not found" }, { status: 404 });
    }

    // Validate currency is Stripe-supported
    const currency = (plan.currency || "USD").toLowerCase();
    if (!["usd", "eur", "gbp"].includes(currency)) {
      return NextResponse.json(
        { error: "This plan uses PayFast (ZAR). Use /api/billing/checkout instead." },
        { status: 400 }
      );
    }

    // Get client details
    const { data: client, error: clientError } = await supabase
      .from("clients")
      .select("id, email, full_name")
      .eq("id", session.profileId)
      .single();

    if (clientError || !client) {
      return NextResponse.json({ error: "Client not found" }, { status: 404 });
    }

    const amount =
      billingInterval === "monthly" ? plan.price_monthly : plan.price_yearly;

    const baseUrl =
      process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

    const checkoutSession = await createCheckoutSession({
      clientId: client.id,
      clientEmail: client.email,
      clientName: client.full_name,
      planName: plan.name,
      amount,
      currency: currency as "usd" | "eur" | "gbp",
      billingInterval,
      planId: plan.id,
      successUrl: `${baseUrl}/portal/billing?payment=success&session_id={CHECKOUT_SESSION_ID}`,
      cancelUrl: `${baseUrl}/portal/billing?payment=cancelled`,
    });

    return NextResponse.json({
      checkoutUrl: checkoutSession.url,
      sessionId: checkoutSession.id,
    });
  } catch (error) {
    console.error("[billing/checkout-stripe] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
