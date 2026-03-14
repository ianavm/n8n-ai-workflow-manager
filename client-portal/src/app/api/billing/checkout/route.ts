import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { generatePaymentData, getPayFastUrl } from "@/lib/payfast";

export const dynamic = "force-dynamic";

// POST /api/billing/checkout — generate PayFast payment redirect data
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

    // Look up plan from DB
    const { data: plan, error: planError } = await supabase
      .from("plans")
      .select("*")
      .eq("slug", planSlug)
      .eq("active", true)
      .single();

    if (planError || !plan) {
      return NextResponse.json(
        { error: "Plan not found" },
        { status: 404 }
      );
    }

    // Get client details
    const { data: client, error: clientError } = await supabase
      .from("clients")
      .select("id, email, full_name")
      .eq("id", session.profileId)
      .single();

    if (clientError || !client) {
      return NextResponse.json(
        { error: "Client not found" },
        { status: 404 }
      );
    }

    // Determine amount based on billing interval
    const amount =
      billingInterval === "monthly"
        ? plan.price_monthly
        : plan.price_yearly;

    const baseUrl = process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

    const paymentData = generatePaymentData({
      clientId: client.id,
      clientEmail: client.email,
      clientName: client.full_name,
      planName: plan.name,
      amount,
      billingInterval,
      returnUrl: `${baseUrl}/billing?status=success`,
      cancelUrl: `${baseUrl}/billing?status=cancelled`,
      notifyUrl: `${baseUrl}/api/webhooks/payfast`,
    });

    // Attach custom fields for webhook identification
    const paymentDataWithCustom: Record<string, string> = {
      ...paymentData,
      custom_str1: client.id,
      custom_str2: plan.id,
    };

    return NextResponse.json({
      paymentUrl: getPayFastUrl(),
      paymentData: paymentDataWithCustom,
    });
  } catch (error) {
    console.error("[billing/checkout] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
