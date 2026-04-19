import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { constructWebhookEvent, getStripe } from "@/lib/stripe";
import type Stripe from "stripe";

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
    console.error("[webhooks/stripe] generate_invoice_number RPC failed, using fallback:", err);
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, "0");
    const ts = now.getTime().toString(36).toUpperCase();
    return `AVM-${year}${month}-${ts}`;
  }
}

// POST /api/webhooks/stripe — Stripe webhook handler
export async function POST(request: NextRequest) {
  try {
    const rawBody = await request.text();
    const signature = request.headers.get("stripe-signature");

    if (!signature) {
      console.error("[webhooks/stripe] Missing stripe-signature header");
      return NextResponse.json({ error: "Missing signature" }, { status: 400 });
    }

    let event: Stripe.Event;
    try {
      event = constructWebhookEvent(rawBody, signature);
    } catch (err) {
      console.error("[webhooks/stripe] Signature verification failed:", err);
      return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
    }

    console.info(`[webhooks/stripe] Event: ${event.type}, ID: ${event.id}`);

    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutComplete(
          event.data.object as Stripe.Checkout.Session
        );
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(
          event.data.object as Stripe.Subscription
        );
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionCanceled(
          event.data.object as Stripe.Subscription
        );
        break;

      case "invoice.paid":
        await handleInvoicePaid(event.data.object as Stripe.Invoice);
        break;

      case "invoice.payment_failed":
        await handleInvoiceFailed(event.data.object as Stripe.Invoice);
        break;

      default:
        console.info(`[webhooks/stripe] Unhandled event: ${event.type}`);
    }

    return NextResponse.json({ received: true }, { status: 200 });
  } catch (error) {
    console.error("[webhooks/stripe] Error:", error);
    // Always return 200 to prevent Stripe retries on our errors
    return NextResponse.json({ received: true }, { status: 200 });
  }
}

// ---------------------------------------------------------------------------
// checkout.session.completed
// ---------------------------------------------------------------------------

async function handleCheckoutComplete(session: Stripe.Checkout.Session) {
  const stripe = getStripe();

  // Retrieve full session with expanded subscription
  const fullSession = await stripe.checkout.sessions.retrieve(session.id, {
    expand: ["subscription"],
  });

  const metadata = fullSession.metadata ?? {};
  const clientId = metadata.client_id;
  const planId = metadata.plan_id;
  const paymentType = metadata.payment_type || "subscription";
  const addonId = metadata.addon_id;

  if (!clientId) {
    console.error("[webhooks/stripe] Missing client_id in session metadata");
    return;
  }

  console.info(
    `[webhooks/stripe] Checkout completed: type=${paymentType}, client=${clientId}`
  );

  // Route by payment type
  if (paymentType === "addon") {
    await handleAddonCheckoutComplete({
      clientId,
      addonId: addonId || planId || "",
      session: fullSession,
    });
    return;
  }

  if (paymentType === "setup_fee") {
    await handleSetupFeeCheckoutComplete({
      clientId,
      setupFeeId: metadata.setup_fee_id || "",
      session: fullSession,
    });
    return;
  }

  // Default: subscription checkout
  if (!planId) {
    console.error("[webhooks/stripe] Missing plan_id for subscription checkout");
    return;
  }

  const stripeSubscription =
    fullSession.subscription as Stripe.Subscription | null;
  const stripeCustomerId =
    typeof fullSession.customer === "string"
      ? fullSession.customer
      : fullSession.customer?.id ?? null;
  const stripeSubscriptionId = stripeSubscription?.id ?? null;
  const currency = (fullSession.currency ?? "usd").toUpperCase();

  // Determine billing interval from Stripe subscription
  const interval =
    stripeSubscription?.items?.data?.[0]?.price?.recurring?.interval;
  const billingInterval = interval === "year" ? "yearly" : "monthly";

  // Calculate period
  const now = new Date();
  const periodStart = now.toISOString();
  const periodEnd = new Date(now);
  if (billingInterval === "yearly") {
    periodEnd.setFullYear(periodEnd.getFullYear() + 1);
  } else {
    periodEnd.setMonth(periodEnd.getMonth() + 1);
  }

  // Trial dates (Stripe handles the 14-day trial)
  const trialEnd = stripeSubscription?.trial_end
    ? new Date(stripeSubscription.trial_end * 1000).toISOString()
    : null;
  const status =
    stripeSubscription?.status === "trialing" ? "trialing" : "active";

  // Get plan name for invoice
  const { data: plan } = await supabaseAdmin
    .from("plans")
    .select("name")
    .eq("id", planId)
    .single();

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
    const { data: updated } = await supabaseAdmin
      .from("subscriptions")
      .update({
        status,
        plan_id: planId,
        billing_interval: billingInterval,
        current_period_start: periodStart,
        current_period_end: periodEnd.toISOString(),
        trial_end: trialEnd,
        cancel_at_period_end: false,
        stripe_customer_id: stripeCustomerId,
        stripe_subscription_id: stripeSubscriptionId,
        updated_at: now.toISOString(),
      })
      .eq("id", existingSub.id)
      .select("id")
      .single();

    subscriptionId = updated?.id || existingSub.id;
  } else {
    const { data: newSub } = await supabaseAdmin
      .from("subscriptions")
      .insert({
        client_id: clientId,
        plan_id: planId,
        status,
        billing_interval: billingInterval,
        current_period_start: periodStart,
        current_period_end: periodEnd.toISOString(),
        trial_end: trialEnd,
        stripe_customer_id: stripeCustomerId,
        stripe_subscription_id: stripeSubscriptionId,
      })
      .select("id")
      .single();

    subscriptionId = newSub?.id || "";
  }

  // Create invoice (only if amount > 0 — trial may be $0)
  const amountTotal = fullSession.amount_total ?? 0;
  if (amountTotal > 0) {
    const invoiceNumber = await generateInvoiceNumber();

    await supabaseAdmin.from("invoices").insert({
      client_id: clientId,
      subscription_id: subscriptionId,
      invoice_number: invoiceNumber,
      status: "paid",
      amount_due: amountTotal,
      amount_paid: amountTotal,
      vat_amount: 0,
      currency,
      stripe_payment_intent_id:
        typeof fullSession.payment_intent === "string"
          ? fullSession.payment_intent
          : fullSession.payment_intent?.id ?? null,
      paid_at: now.toISOString(),
      description: plan
        ? `${plan.name} - ${billingInterval}`
        : "Subscription payment",
    });

    console.info(`[webhooks/stripe] Invoice created: ${invoiceNumber}`);
  }

  // Log activity
  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "checkout_complete",
    target_type: "subscription",
    target_id: subscriptionId,
    details: {
      client_id: clientId,
      plan_id: planId,
      stripe_customer_id: stripeCustomerId,
      stripe_subscription_id: stripeSubscriptionId,
      amount_total: amountTotal,
      currency,
    },
  });

  console.info(
    `[webhooks/stripe] Subscription ${status}: client=${clientId}, plan=${plan?.name}`
  );
}

// ---------------------------------------------------------------------------
// customer.subscription.updated
// ---------------------------------------------------------------------------

async function handleSubscriptionUpdated(subscription: Stripe.Subscription) {
  const stripeSubId = subscription.id;

  const { data: existingSub } = await supabaseAdmin
    .from("subscriptions")
    .select("id, client_id")
    .eq("stripe_subscription_id", stripeSubId)
    .maybeSingle();

  if (!existingSub) {
    console.info(
      `[webhooks/stripe] No local subscription for stripe_subscription_id=${stripeSubId}`
    );
    return;
  }

  // Map Stripe status to our status
  const statusMap: Record<string, string> = {
    active: "active",
    trialing: "trialing",
    past_due: "past_due",
    canceled: "canceled",
    unpaid: "past_due",
    incomplete: "past_due",
    incomplete_expired: "canceled",
    paused: "canceled",
  };

  const newStatus = statusMap[subscription.status] || "active";

  // Use safe access — Stripe SDK types vary between versions
  const subData = subscription as unknown as Record<string, unknown>;
  const rawStart = subData.current_period_start as number | undefined;
  const rawEnd = subData.current_period_end as number | undefined;
  const periodStart = rawStart
    ? new Date(rawStart * 1000).toISOString()
    : undefined;
  const periodEnd = rawEnd
    ? new Date(rawEnd * 1000).toISOString()
    : undefined;

  await supabaseAdmin
    .from("subscriptions")
    .update({
      status: newStatus,
      current_period_start: periodStart,
      current_period_end: periodEnd,
      cancel_at_period_end: subscription.cancel_at_period_end,
      updated_at: new Date().toISOString(),
    })
    .eq("id", existingSub.id);

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "subscription_updated",
    target_type: "subscription",
    target_id: existingSub.id,
    details: {
      client_id: existingSub.client_id,
      stripe_status: subscription.status,
      local_status: newStatus,
      cancel_at_period_end: subscription.cancel_at_period_end,
    },
  });

  console.info(
    `[webhooks/stripe] Subscription updated: ${stripeSubId} -> ${newStatus}`
  );
}

// ---------------------------------------------------------------------------
// customer.subscription.deleted
// ---------------------------------------------------------------------------

async function handleSubscriptionCanceled(subscription: Stripe.Subscription) {
  const stripeSubId = subscription.id;

  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id, client_id")
    .eq("stripe_subscription_id", stripeSubId)
    .maybeSingle();

  if (!sub) return;

  await supabaseAdmin
    .from("subscriptions")
    .update({
      status: "canceled",
      canceled_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", sub.id);

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "subscription_canceled",
    target_type: "subscription",
    target_id: sub.id,
    details: { client_id: sub.client_id },
  });

  console.info(
    `[webhooks/stripe] Subscription canceled: client=${sub.client_id}`
  );
}

// ---------------------------------------------------------------------------
// invoice.paid — recurring payments after initial checkout
// ---------------------------------------------------------------------------

async function handleInvoicePaid(invoice: Stripe.Invoice) {
  // Skip the first invoice (already handled in checkout.session.completed)
  if (invoice.billing_reason === "subscription_create") return;

  // Safe access — Stripe SDK types vary between versions
  const invoiceData = invoice as unknown as Record<string, unknown>;
  const rawSub = invoiceData.subscription;
  const stripeSubscriptionId =
    typeof rawSub === "string"
      ? rawSub
      : (rawSub as Record<string, unknown> | null)?.id as string | null ?? null;

  if (!stripeSubscriptionId) return;

  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id, client_id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .maybeSingle();

  if (!sub) return;

  // Activate subscription (trial -> active after first real payment)
  await supabaseAdmin
    .from("subscriptions")
    .update({
      status: "active",
      updated_at: new Date().toISOString(),
    })
    .eq("id", sub.id);

  // Create invoice record
  const amountPaid = (invoiceData.amount_paid as number) ?? 0;
  if (amountPaid <= 0) return;

  const invoiceNumber = await generateInvoiceNumber();
  const currency = ((invoiceData.currency as string) ?? "usd").toUpperCase();
  const rawPI = invoiceData.payment_intent;
  const paymentIntentId =
    typeof rawPI === "string"
      ? rawPI
      : (rawPI as Record<string, unknown> | null)?.id as string | null ?? null;

  await supabaseAdmin.from("invoices").insert({
    client_id: sub.client_id,
    subscription_id: sub.id,
    invoice_number: invoiceNumber,
    status: "paid",
    amount_due: amountPaid,
    amount_paid: amountPaid,
    vat_amount: 0,
    currency,
    stripe_invoice_id: invoice.id,
    stripe_payment_intent_id: paymentIntentId,
    paid_at: new Date().toISOString(),
    description: `Recurring payment (${currency})`,
  });

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "recurring_payment",
    target_type: "subscription",
    target_id: sub.id,
    details: {
      client_id: sub.client_id,
      amount_paid: amountPaid,
      currency,
      invoice_number: invoiceNumber,
    },
  });

  console.info(
    `[webhooks/stripe] Invoice paid: client=${sub.client_id}, ${currency} ${amountPaid / 100}`
  );
}

// ---------------------------------------------------------------------------
// invoice.payment_failed
// ---------------------------------------------------------------------------

async function handleInvoiceFailed(invoice: Stripe.Invoice) {
  // Safe access — Stripe SDK types vary between versions
  const invoiceData = invoice as unknown as Record<string, unknown>;
  const rawSub = invoiceData.subscription;
  const stripeSubscriptionId =
    typeof rawSub === "string"
      ? rawSub
      : (rawSub as Record<string, unknown> | null)?.id as string | null ?? null;

  if (!stripeSubscriptionId) return;

  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id, client_id")
    .eq("stripe_subscription_id", stripeSubscriptionId)
    .maybeSingle();

  if (!sub) return;

  // Set subscription to past_due
  await supabaseAdmin
    .from("subscriptions")
    .update({
      status: "past_due",
      updated_at: new Date().toISOString(),
    })
    .eq("id", sub.id);

  // Create open invoice
  const amountDue = (invoiceData.amount_due as number) ?? 0;
  const currency = ((invoiceData.currency as string) ?? "usd").toUpperCase();

  await supabaseAdmin.from("invoices").insert({
    client_id: sub.client_id,
    subscription_id: sub.id,
    invoice_number: await generateInvoiceNumber(),
    status: "open",
    amount_due: amountDue,
    amount_paid: 0,
    vat_amount: 0,
    currency,
    stripe_invoice_id: invoice.id,
    description: "Payment failed",
  });

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "payment_failed",
    target_type: "subscription",
    target_id: sub.id,
    details: {
      client_id: sub.client_id,
      amount_due: amountDue,
      currency,
    },
  });

  console.info(`[webhooks/stripe] Payment failed: client=${sub.client_id}`);
}

// ---------------------------------------------------------------------------
// Add-on checkout completed
// ---------------------------------------------------------------------------

async function handleAddonCheckoutComplete(params: {
  clientId: string;
  addonId: string;
  session: Stripe.Checkout.Session;
}) {
  const { clientId, addonId, session } = params;

  const { data: sub } = await supabaseAdmin
    .from("subscriptions")
    .select("id")
    .eq("client_id", clientId)
    .in("status", ["active", "trialing", "past_due"])
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();

  if (!sub) {
    console.error(
      `[webhooks/stripe] No active subscription for addon: client=${clientId}`
    );
    return;
  }

  const stripeSubId =
    typeof session.subscription === "string"
      ? session.subscription
      : (session.subscription as Stripe.Subscription | null)?.id ?? null;

  // Activate add-on (upsert)
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
        stripe_subscription_id: stripeSubId,
        activated_at: new Date().toISOString(),
        deactivated_at: null,
      })
      .eq("id", existing.id);
  } else {
    await supabaseAdmin.from("subscription_addons").insert({
      subscription_id: sub.id,
      addon_id: addonId,
      status: "active",
      stripe_subscription_id: stripeSubId,
      activated_at: new Date().toISOString(),
    });
  }

  // Create invoice
  const amountTotal = session.amount_total ?? 0;
  if (amountTotal > 0) {
    const invoiceNumber = await generateInvoiceNumber();
    const currency = (session.currency ?? "usd").toUpperCase();

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
      amount_due: amountTotal,
      amount_paid: amountTotal,
      vat_amount: 0,
      currency,
      stripe_payment_intent_id:
        typeof session.payment_intent === "string"
          ? session.payment_intent
          : session.payment_intent?.id ?? null,
      paid_at: new Date().toISOString(),
      description: `Add-on: ${addon?.name || addonId}`,
    });
  }

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "addon_payment_complete",
    target_type: "addon",
    target_id: addonId,
    details: { client_id: clientId, amount_total: session.amount_total },
  });

  console.info(
    `[webhooks/stripe] Addon activated: client=${clientId}, addon=${addonId}`
  );
}

// ---------------------------------------------------------------------------
// Setup fee checkout completed
// ---------------------------------------------------------------------------

async function handleSetupFeeCheckoutComplete(params: {
  clientId: string;
  setupFeeId: string;
  session: Stripe.Checkout.Session;
}) {
  const { clientId, setupFeeId, session } = params;

  // Mark setup fee as paid
  await supabaseAdmin
    .from("setup_fees")
    .update({
      status: "paid",
      paid_at: new Date().toISOString(),
    })
    .eq("id", setupFeeId)
    .eq("client_id", clientId);

  // Create invoice
  const amountTotal = session.amount_total ?? 0;
  const invoiceNumber = await generateInvoiceNumber();
  const currency = (session.currency ?? "usd").toUpperCase();

  const { data: fee } = await supabaseAdmin
    .from("setup_fees")
    .select("service_type, description")
    .eq("id", setupFeeId)
    .single();

  await supabaseAdmin.from("invoices").insert({
    client_id: clientId,
    invoice_number: invoiceNumber,
    status: "paid",
    amount_due: amountTotal,
    amount_paid: amountTotal,
    vat_amount: 0,
    currency,
    stripe_payment_intent_id:
      typeof session.payment_intent === "string"
        ? session.payment_intent
        : session.payment_intent?.id ?? null,
    paid_at: new Date().toISOString(),
    description: `Setup fee: ${fee?.description || fee?.service_type || setupFeeId}`,
  });

  await supabaseAdmin.from("activity_log").insert({
    actor_type: "system",
    actor_id: "stripe",
    action: "setup_fee_paid",
    target_type: "setup_fee",
    target_id: setupFeeId,
    details: {
      client_id: clientId,
      amount_total: amountTotal,
      currency,
      invoice_number: invoiceNumber,
    },
  });

  console.info(
    `[webhooks/stripe] Setup fee paid: client=${clientId}, fee=${setupFeeId}`
  );
}
