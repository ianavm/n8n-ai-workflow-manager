import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateITN, confirmWithPayFast } from "@/lib/payfast";

export const dynamic = "force-dynamic";

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

function generateInvoiceNumber(): string {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const seq = String(Math.floor(Math.random() * 9999) + 1).padStart(4, "0");
  return `AVM-${year}${month}-${seq}`;
}

// POST /api/webhooks/payfast — PayFast ITN handler
export async function POST(request: NextRequest) {
  try {
    // Parse form-encoded body
    const formData = await request.formData();
    const data: Record<string, string> = {};
    formData.forEach((value, key) => {
      data[key] = value.toString();
    });

    console.log("[webhooks/payfast] ITN received:", {
      payment_status: data.payment_status,
      m_payment_id: data.m_payment_id,
      pf_payment_id: data.pf_payment_id,
      custom_str1: data.custom_str1,
      custom_str2: data.custom_str2,
    });

    // Step 1: Validate ITN signature
    if (!validateITN(data)) {
      console.error("[webhooks/payfast] Invalid ITN signature");
      return new NextResponse("INVALID SIGNATURE", { status: 200 });
    }

    // Step 2: Confirm with PayFast server
    const paramString = Array.from(formData.entries())
      .map(([key, val]) => `${encodeURIComponent(key)}=${encodeURIComponent(val.toString())}`)
      .join("&");

    const isValid = await confirmWithPayFast(paramString);
    if (!isValid) {
      console.error("[webhooks/payfast] PayFast server confirmation failed");
      return new NextResponse("CONFIRMATION FAILED", { status: 200 });
    }

    // Step 3: Extract identifiers
    const clientId = data.custom_str1;
    const planId = data.custom_str2;
    const paymentStatus = data.payment_status;
    const pfPaymentId = data.pf_payment_id;
    const amountGross = data.amount_gross;
    const amountFee = data.amount_fee;
    const amountNet = data.amount_net;
    const mPaymentId = data.m_payment_id;
    const payfastToken = data.token;

    if (!clientId || !planId) {
      console.error("[webhooks/payfast] Missing custom_str1 (client_id) or custom_str2 (plan_id)");
      return new NextResponse("MISSING IDENTIFIERS", { status: 200 });
    }

    // Step 4: Handle payment status
    if (paymentStatus === "COMPLETE") {
      await handlePaymentComplete({
        clientId,
        planId,
        pfPaymentId,
        mPaymentId,
        amountGross,
        amountFee,
        amountNet,
        payfastToken,
        billingDate: data.billing_date,
      });
    } else if (paymentStatus === "FAILED") {
      await handlePaymentFailed({
        clientId,
        planId,
        pfPaymentId,
        mPaymentId,
        amountGross,
      });
    } else if (paymentStatus === "CANCELLED") {
      await handlePaymentCancelled({ clientId });
    } else {
      console.log(`[webhooks/payfast] Unhandled payment_status: ${paymentStatus}`);
    }

    // PayFast requires a 200 OK response
    return new NextResponse("OK", { status: 200 });
  } catch (error) {
    console.error("[webhooks/payfast] Error:", error);
    // Still return 200 to avoid PayFast retries on our errors
    return new NextResponse("ERROR", { status: 200 });
  }
}

// ---------------------------------------------------------------------------
// Handlers
// ---------------------------------------------------------------------------

interface PaymentCompleteParams {
  clientId: string;
  planId: string;
  pfPaymentId: string;
  mPaymentId: string;
  amountGross: string;
  amountFee: string;
  amountNet: string;
  payfastToken?: string;
  billingDate?: string;
}

async function handlePaymentComplete(params: PaymentCompleteParams) {
  const {
    clientId,
    planId,
    pfPaymentId,
    mPaymentId,
    amountGross,
    amountFee,
    amountNet,
    payfastToken,
    billingDate,
  } = params;

  // Get plan details for billing interval
  const { data: plan } = await supabaseAdmin
    .from("plans")
    .select("*")
    .eq("id", planId)
    .single();

  // Determine billing interval from m_payment_id or plan
  const isYearly = mPaymentId?.includes("yearly") || false;
  const billingInterval = isYearly ? "yearly" : "monthly";

  // Calculate current period
  const now = new Date();
  const periodStart = now.toISOString();
  const periodEnd = new Date(now);
  if (billingInterval === "yearly") {
    periodEnd.setFullYear(periodEnd.getFullYear() + 1);
  } else {
    periodEnd.setMonth(periodEnd.getMonth() + 1);
  }

  // Find or create subscription
  const { data: existingSub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("client_id", clientId)
    .in("status", ["active", "trialing", "past_due"])
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  let subscriptionId: string;

  if (existingSub) {
    // Update existing subscription
    const { data: updated } = await supabaseAdmin
      .from("subscriptions")
      .update({
        status: "active",
        plan_id: planId,
        billing_interval: billingInterval,
        current_period_start: periodStart,
        current_period_end: periodEnd.toISOString(),
        cancel_at_period_end: false,
        payfast_token: payfastToken || undefined,
        updated_at: now.toISOString(),
      })
      .eq("id", existingSub.id)
      .select("id")
      .single();

    subscriptionId = updated?.id || existingSub.id;
  } else {
    // Create new subscription (first payment)
    const { data: newSub } = await supabaseAdmin
      .from("subscriptions")
      .insert({
        client_id: clientId,
        plan_id: planId,
        status: "active",
        billing_interval: billingInterval,
        current_period_start: periodStart,
        current_period_end: periodEnd.toISOString(),
        payfast_token: payfastToken || null,
      })
      .select("id")
      .single();

    subscriptionId = newSub?.id || "";
  }

  // Create invoice (status = paid)
  const invoiceNumber = generateInvoiceNumber();
  const amountCents = Math.round(parseFloat(amountGross) * 100);
  const feeCents = Math.round(parseFloat(amountFee || "0") * 100);
  const netCents = Math.round(parseFloat(amountNet || amountGross) * 100);

  await supabaseAdmin.from("invoices").insert({
    client_id: clientId,
    subscription_id: subscriptionId,
    invoice_number: invoiceNumber,
    status: "paid",
    amount: amountCents,
    fee: feeCents,
    net_amount: netCents,
    currency: "ZAR",
    payfast_payment_id: pfPaymentId,
    m_payment_id: mPaymentId,
    paid_at: now.toISOString(),
    description: plan ? `${plan.name} - ${billingInterval}` : `Subscription payment`,
  });

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "payfast",
    action: "payment_complete",
    target_type: "subscription",
    target_id: subscriptionId,
    details: {
      client_id: clientId,
      plan_id: planId,
      pf_payment_id: pfPaymentId,
      amount_gross: amountGross,
      invoice_number: invoiceNumber,
    },
  });

  console.log(`[webhooks/payfast] Payment complete: client=${clientId}, invoice=${invoiceNumber}`);
}

interface PaymentFailedParams {
  clientId: string;
  planId: string;
  pfPaymentId: string;
  mPaymentId: string;
  amountGross: string;
}

async function handlePaymentFailed(params: PaymentFailedParams) {
  const { clientId, planId, pfPaymentId, mPaymentId, amountGross } = params;

  // Set subscription to past_due
  const { data: existingSub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("client_id", clientId)
    .in("status", ["active", "trialing"])
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (existingSub) {
    await supabaseAdmin
      .from("subscriptions")
      .update({
        status: "past_due",
        updated_at: new Date().toISOString(),
      })
      .eq("id", existingSub.id);
  }

  // Create invoice (status = open — payment failed)
  const amountCents = Math.round(parseFloat(amountGross) * 100);

  await supabaseAdmin.from("invoices").insert({
    client_id: clientId,
    subscription_id: existingSub?.id || null,
    invoice_number: generateInvoiceNumber(),
    status: "open",
    amount: amountCents,
    currency: "ZAR",
    payfast_payment_id: pfPaymentId,
    m_payment_id: mPaymentId,
    description: "Payment failed",
  });

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "payfast",
    action: "payment_failed",
    target_type: "subscription",
    target_id: existingSub?.id || clientId,
    details: {
      client_id: clientId,
      plan_id: planId,
      pf_payment_id: pfPaymentId,
      amount_gross: amountGross,
    },
  });

  console.log(`[webhooks/payfast] Payment failed: client=${clientId}`);
}

interface PaymentCancelledParams {
  clientId: string;
}

async function handlePaymentCancelled(params: PaymentCancelledParams) {
  const { clientId } = params;

  // Set subscription to canceled
  const { data: existingSub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("client_id", clientId)
    .in("status", ["active", "trialing", "past_due"])
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (existingSub) {
    await supabaseAdmin
      .from("subscriptions")
      .update({
        status: "canceled",
        canceled_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("id", existingSub.id);
  }

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "payfast",
    action: "payment_cancelled",
    target_type: "subscription",
    target_id: existingSub?.id || clientId,
    details: { client_id: clientId },
  });

  console.log(`[webhooks/payfast] Payment cancelled: client=${clientId}`);
}
