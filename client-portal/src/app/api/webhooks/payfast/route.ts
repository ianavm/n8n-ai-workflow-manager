import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { validateITN, confirmWithPayFast } from "@/lib/payfast";

export const dynamic = "force-dynamic";

const supabaseAdmin = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

async function generateInvoiceNumber(): Promise<string> {
  try {
    const { data, error } = await supabaseAdmin.rpc("generate_invoice_number");
    if (error) throw error;
    return data as string;
  } catch (err) {
    console.error("[webhooks/payfast] generate_invoice_number RPC failed, using fallback:", err);
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const ts = now.getTime().toString(36).toUpperCase();
    return `AVM-${year}${month}-${ts}`;
  }
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

    console.info("[webhooks/payfast] ITN received:", {
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
    const paymentType = data.custom_str3 || "subscription"; // subscription | addon | setup_fee
    const paymentStatus = data.payment_status;
    const pfPaymentId = data.pf_payment_id;
    const amountGross = data.amount_gross;
    const amountFee = data.amount_fee;
    const amountNet = data.amount_net;
    const mPaymentId = data.m_payment_id;
    const payfastToken = data.token;

    if (!clientId) {
      console.error("[webhooks/payfast] Missing custom_str1 (client_id)");
      return new NextResponse("MISSING IDENTIFIERS", { status: 200 });
    }

    console.info(`[webhooks/payfast] Payment type: ${paymentType}`);

    // Step 4: Handle payment status
    if (paymentStatus === "COMPLETE") {
      if (paymentType === "addon") {
        await handleAddonPaymentComplete({
          clientId,
          addonId: planId, // custom_str2 holds addon_id for add-on payments
          pfPaymentId,
          amountGross,
          payfastToken,
        });
      } else if (paymentType === "setup_fee") {
        await handleSetupFeePaymentComplete({
          clientId,
          setupFeeId: planId, // custom_str2 holds setup_fee_id
          pfPaymentId,
          amountGross,
        });
      } else {
        // Default: subscription payment
        if (!planId) {
          console.error("[webhooks/payfast] Missing custom_str2 (plan_id) for subscription payment");
          return new NextResponse("MISSING PLAN ID", { status: 200 });
        }
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
      }
    } else if (paymentStatus === "FAILED") {
      await handlePaymentFailed({
        clientId,
        planId: planId || "",
        pfPaymentId,
        mPaymentId,
        amountGross,
      });
    } else if (paymentStatus === "CANCELLED") {
      await handlePaymentCancelled({ clientId, pfPaymentId });
    } else {
      console.info(`[webhooks/payfast] Unhandled payment_status: ${paymentStatus}`);
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
  const invoiceNumber = await generateInvoiceNumber();
  const amountCents = Math.round(parseFloat(amountGross) * 100);
  const vatCents = Math.round(amountCents * 15 / 115); // Extract 15% VAT from gross

  // Skip if this payment was already recorded (idempotency)
  const { data: existingInvoice } = await supabaseAdmin
    .from("invoices")
    .select("id")
    .eq("payfast_payment_id", pfPaymentId)
    .maybeSingle();

  if (!existingInvoice) {
    await supabaseAdmin.from("invoices").insert({
      client_id: clientId,
      subscription_id: subscriptionId,
      invoice_number: invoiceNumber,
      status: "paid",
      amount_due: amountCents,
      amount_paid: amountCents,
      vat_amount: vatCents,
      currency: "ZAR",
      payfast_payment_id: pfPaymentId,
      paid_at: now.toISOString(),
      description: plan ? `${plan.name} - ${billingInterval}` : `Subscription payment`,
    });
  }

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

  console.info(`[webhooks/payfast] Payment complete: client=${clientId}, invoice=${invoiceNumber}`);
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

  // Idempotency: skip if this payment was already recorded
  const { data: existingInvoice } = await supabaseAdmin
    .from("invoices")
    .select("id")
    .eq("payfast_payment_id", pfPaymentId)
    .maybeSingle();

  if (existingInvoice) {
    console.info(`[webhooks/payfast] Duplicate payment_failed skipped: pf_payment_id=${pfPaymentId}`);
    return;
  }

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
    invoice_number: await generateInvoiceNumber(),
    status: "open",
    amount_due: amountCents,
    amount_paid: 0,
    vat_amount: 0,
    currency: "ZAR",
    payfast_payment_id: pfPaymentId,
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

  console.info(`[webhooks/payfast] Payment failed: client=${clientId}`);
}

interface PaymentCancelledParams {
  clientId: string;
  pfPaymentId: string;
}

async function handlePaymentCancelled(params: PaymentCancelledParams) {
  const { clientId, pfPaymentId } = params;

  // Idempotency: skip if this cancellation was already processed
  if (pfPaymentId) {
    const { data: existingLog } = await supabaseAdmin
      .from("activity_log")
      .select("id")
      .eq("action", "payment_cancelled")
      .contains("details", { pf_payment_id: pfPaymentId })
      .maybeSingle();

    if (existingLog) {
      console.info(`[webhooks/payfast] Duplicate payment_cancelled skipped: pf_payment_id=${pfPaymentId}`);
      return;
    }
  }

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
    details: { client_id: clientId, pf_payment_id: pfPaymentId },
  });

  console.info(`[webhooks/payfast] Payment cancelled: client=${clientId}`);
}

// ---------------------------------------------------------------------------
// Add-on payment handler
// ---------------------------------------------------------------------------

interface AddonPaymentCompleteParams {
  clientId: string;
  addonId: string;
  pfPaymentId: string;
  amountGross: string;
  payfastToken?: string;
}

async function handleAddonPaymentComplete(params: AddonPaymentCompleteParams) {
  const { clientId, addonId, pfPaymentId, amountGross, payfastToken } = params;

  // Idempotency: skip if this payment was already recorded
  const { data: existingInvoice } = await supabaseAdmin
    .from("invoices")
    .select("id")
    .eq("payfast_payment_id", pfPaymentId)
    .maybeSingle();

  if (existingInvoice) {
    console.info(`[webhooks/payfast] Duplicate addon payment skipped: pf_payment_id=${pfPaymentId}`);
    return;
  }

  // Get current subscription
  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("client_id", clientId)
    .in("status", ["active", "trialing", "past_due"])
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (!sub) {
    console.error(`[webhooks/payfast] No active subscription for addon payment: client=${clientId}`);
    return;
  }

  // Activate the add-on (update if exists, insert if not)
  const { data: existing } = await supabaseAdmin
    .from("subscription_addons")
    .select("id")
    .eq("subscription_id", sub.id)
    .eq("addon_id", addonId)
    .maybeSingle();

  if (existing) {
    await supabaseAdmin
      .from("subscription_addons")
      .update({
        status: "active",
        payfast_token: payfastToken || null,
        activated_at: new Date().toISOString(),
        deactivated_at: null,
      })
      .eq("id", existing.id);
  } else {
    await supabaseAdmin
      .from("subscription_addons")
      .insert({
        subscription_id: sub.id,
        addon_id: addonId,
        status: "active",
        payfast_token: payfastToken || null,
        activated_at: new Date().toISOString(),
      });
  }

  // Create invoice for addon payment
  const amountCents = Math.round(parseFloat(amountGross) * 100);
  const invoiceNumber = await generateInvoiceNumber();

  const { data: addon } = await supabaseAdmin
    .from("addons")
    .select("name")
    .eq("id", addonId)
    .single();

  await supabaseAdmin.from("invoices").insert({
    client_id: clientId,
    subscription_id: sub.id,
    invoice_number: invoiceNumber,
    status: "paid",
    amount_due: amountCents,
    amount_paid: amountCents,
    vat_amount: Math.round(amountCents * 15 / 115),
    currency: "ZAR",
    payfast_payment_id: pfPaymentId,
    paid_at: new Date().toISOString(),
    description: `Add-on: ${addon?.name || addonId}`,
  });

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "payfast",
    action: "addon_payment_complete",
    target_type: "addon",
    target_id: addonId,
    details: {
      client_id: clientId,
      addon_name: addon?.name,
      amount_gross: amountGross,
      invoice_number: invoiceNumber,
    },
  });

  console.info(`[webhooks/payfast] Addon payment complete: client=${clientId}, addon=${addon?.name}`);
}

// ---------------------------------------------------------------------------
// Setup fee payment handler
// ---------------------------------------------------------------------------

interface SetupFeePaymentCompleteParams {
  clientId: string;
  setupFeeId: string;
  pfPaymentId: string;
  amountGross: string;
}

async function handleSetupFeePaymentComplete(params: SetupFeePaymentCompleteParams) {
  const { clientId, setupFeeId, pfPaymentId, amountGross } = params;

  // Idempotency: skip if this payment was already recorded
  const { data: existingInvoice } = await supabaseAdmin
    .from("invoices")
    .select("id")
    .eq("payfast_payment_id", pfPaymentId)
    .maybeSingle();

  if (existingInvoice) {
    console.info(`[webhooks/payfast] Duplicate setup_fee payment skipped: pf_payment_id=${pfPaymentId}`);
    return;
  }

  // Mark setup fee as paid
  await supabaseAdmin
    .from("setup_fees")
    .update({
      status: "paid",
      payfast_payment_id: pfPaymentId,
      paid_at: new Date().toISOString(),
    })
    .eq("id", setupFeeId)
    .eq("client_id", clientId);

  // Create invoice
  const amountCents = Math.round(parseFloat(amountGross) * 100);
  const invoiceNumber = await generateInvoiceNumber();

  const { data: fee } = await supabaseAdmin
    .from("setup_fees")
    .select("service_type, description")
    .eq("id", setupFeeId)
    .single();

  await supabaseAdmin.from("invoices").insert({
    client_id: clientId,
    invoice_number: invoiceNumber,
    status: "paid",
    amount_due: amountCents,
    amount_paid: amountCents,
    vat_amount: Math.round(amountCents * 15 / 115),
    currency: "ZAR",
    payfast_payment_id: pfPaymentId,
    paid_at: new Date().toISOString(),
    description: `Setup fee: ${fee?.description || fee?.service_type || setupFeeId}`,
  });

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "payfast",
    action: "setup_fee_paid",
    target_type: "setup_fee",
    target_id: setupFeeId,
    details: {
      client_id: clientId,
      service_type: fee?.service_type,
      amount_gross: amountGross,
      invoice_number: invoiceNumber,
    },
  });

  console.info(`[webhooks/payfast] Setup fee paid: client=${clientId}, fee=${setupFeeId}`);
}
