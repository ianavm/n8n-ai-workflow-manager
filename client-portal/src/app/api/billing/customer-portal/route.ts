import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { createCustomerPortalSession } from "@/lib/stripe";

export const dynamic = "force-dynamic";

// POST /api/billing/customer-portal — create Stripe Customer Portal session
export async function POST() {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Get subscription with Stripe customer ID
    const { data: subscription } = await supabase
      .from("subscriptions")
      .select("stripe_customer_id")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing", "past_due"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (!subscription?.stripe_customer_id) {
      return NextResponse.json(
        { error: "No Stripe customer found. This feature is only available for international payments." },
        { status: 400 }
      );
    }

    const baseUrl =
      process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

    const portalSession = await createCustomerPortalSession(
      subscription.stripe_customer_id,
      `${baseUrl}/portal/billing`
    );

    return NextResponse.json({ url: portalSession.url });
  } catch (error) {
    console.error("[billing/customer-portal] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
