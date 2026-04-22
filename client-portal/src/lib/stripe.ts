import Stripe from "stripe";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY ?? "";
const STRIPE_WEBHOOK_SECRET = process.env.STRIPE_WEBHOOK_SECRET ?? "";

let _stripe: Stripe | null = null;

/**
 * Returns a singleton Stripe client instance.
 */
export function getStripe(): Stripe {
  if (_stripe) return _stripe;

  if (!STRIPE_SECRET_KEY) {
    throw new Error("Missing STRIPE_SECRET_KEY environment variable");
  }

  _stripe = new Stripe(STRIPE_SECRET_KEY, {
    apiVersion: "2026-02-25.clover",
    typescript: true,
  });

  return _stripe;
}

export function getStripeWebhookSecret(): string {
  return STRIPE_WEBHOOK_SECRET;
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StripeCheckoutParams {
  clientId: string;
  clientEmail: string;
  clientName: string;
  planName: string;
  /** Price in smallest currency unit (cents/pence) */
  amount: number;
  currency: "usd" | "eur" | "gbp";
  billingInterval: "monthly" | "yearly";
  successUrl: string;
  cancelUrl: string;
  /** Supabase plan ID for webhook identification */
  planId: string;
  /** Optional add-on ID */
  addonId?: string;
  /** Payment type for webhook routing */
  paymentType?: "subscription" | "addon" | "setup_fee";
}

// ---------------------------------------------------------------------------
// Checkout Session
// ---------------------------------------------------------------------------

/**
 * Creates a Stripe Checkout session for subscription billing.
 * Uses Stripe's hosted payment page — no card data touches our servers.
 */
export async function createCheckoutSession(
  params: StripeCheckoutParams
): Promise<Stripe.Checkout.Session> {
  const stripe = getStripe();

  const {
    clientId,
    clientEmail,
    clientName,
    planName,
    amount,
    currency,
    billingInterval,
    successUrl,
    cancelUrl,
    planId,
    addonId,
    paymentType = "subscription",
  } = params;

  const intervalMap: Record<string, "month" | "year"> = {
    monthly: "month",
    yearly: "year",
  };

  const session = await stripe.checkout.sessions.create({
    mode: "subscription",
    payment_method_types: ["card"],
    customer_email: clientEmail,
    subscription_data: {
      trial_period_days: 14,
      metadata: {
        client_id: clientId,
        plan_id: planId,
        payment_type: paymentType,
        addon_id: addonId || "",
      },
    },
    line_items: [
      {
        price_data: {
          currency,
          unit_amount: amount,
          product_data: {
            name: `AnyVision ${planName} - ${billingInterval === "monthly" ? "Monthly" : "Yearly"}`,
            description: `${planName} subscription for AnyVision Media AI automation`,
          },
          recurring: {
            interval: intervalMap[billingInterval],
          },
        },
        quantity: 1,
      },
    ],
    success_url: successUrl,
    cancel_url: cancelUrl,
    metadata: {
      client_id: clientId,
      client_name: clientName,
      plan_id: planId,
      payment_type: paymentType,
      addon_id: addonId || "",
    },
    allow_promotion_codes: true,
  });

  return session;
}

/**
 * Creates a one-time Stripe Checkout session (for setup fees).
 */
export async function createOneTimeCheckout(params: {
  clientId: string;
  clientEmail: string;
  description: string;
  amount: number;
  currency: "usd" | "eur" | "gbp";
  setupFeeId: string;
  successUrl: string;
  cancelUrl: string;
}): Promise<Stripe.Checkout.Session> {
  const stripe = getStripe();

  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    payment_method_types: ["card"],
    customer_email: params.clientEmail,
    line_items: [
      {
        price_data: {
          currency: params.currency,
          unit_amount: params.amount,
          product_data: {
            name: params.description,
            description: "One-time setup fee for AnyVision Media",
          },
        },
        quantity: 1,
      },
    ],
    success_url: params.successUrl,
    cancel_url: params.cancelUrl,
    metadata: {
      client_id: params.clientId,
      payment_type: "setup_fee",
      setup_fee_id: params.setupFeeId,
    },
  });

  return session;
}

// ---------------------------------------------------------------------------
// Webhook verification
// ---------------------------------------------------------------------------

/**
 * Verifies and constructs a Stripe webhook event from the raw body + signature.
 */
export function constructWebhookEvent(
  rawBody: string | Buffer,
  signature: string
): Stripe.Event {
  const stripe = getStripe();
  const secret = getStripeWebhookSecret();

  if (!secret) {
    throw new Error("Missing STRIPE_WEBHOOK_SECRET");
  }

  return stripe.webhooks.constructEvent(rawBody, signature, secret);
}

// ---------------------------------------------------------------------------
// Customer Portal
// ---------------------------------------------------------------------------

/**
 * Creates a Stripe Customer Portal session for managing payment methods
 * and viewing invoices.
 */
export async function createCustomerPortalSession(
  customerId: string,
  returnUrl: string
): Promise<Stripe.BillingPortal.Session> {
  const stripe = getStripe();
  return stripe.billingPortal.sessions.create({
    customer: customerId,
    return_url: returnUrl,
  });
}

// ---------------------------------------------------------------------------
// Currency helpers
// ---------------------------------------------------------------------------

export type SupportedCurrency = "ZAR" | "USD" | "EUR" | "GBP";

const CURRENCY_CONFIG: Record<
  SupportedCurrency,
  { symbol: string; locale: string; processor: "payfast" | "stripe" }
> = {
  ZAR: { symbol: "R", locale: "en-ZA", processor: "payfast" },
  USD: { symbol: "$", locale: "en-US", processor: "stripe" },
  EUR: { symbol: "\u20AC", locale: "de-DE", processor: "stripe" },
  GBP: { symbol: "\u00A3", locale: "en-GB", processor: "stripe" },
};

/**
 * Format cents to a display string in the given currency.
 */
export function formatCurrency(cents: number, currency: SupportedCurrency): string {
  const config = CURRENCY_CONFIG[currency];
  if (!config) return `${cents / 100}`;

  const amount = cents / 100;
  const formatted = amount.toLocaleString(config.locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });

  return `${config.symbol}${formatted}`;
}

/**
 * Returns which payment processor to use for a currency.
 */
export function getProcessorForCurrency(
  currency: SupportedCurrency
): "payfast" | "stripe" {
  return CURRENCY_CONFIG[currency]?.processor ?? "stripe";
}

/**
 * Detect likely currency from browser locale or timezone.
 * Falls back to ZAR.
 */
export function detectCurrencyFromLocale(locale: string): SupportedCurrency {
  const lower = locale.toLowerCase();

  if (lower.includes("za") || lower.includes("africa")) return "ZAR";
  if (lower.includes("us") || lower.includes("en-us")) return "USD";
  if (
    lower.includes("de") ||
    lower.includes("fr") ||
    lower.includes("es") ||
    lower.includes("it") ||
    lower.includes("nl") ||
    lower.includes("pt") ||
    lower.includes("at") ||
    lower.includes("be")
  )
    return "EUR";
  if (lower.includes("gb") || lower.includes("en-gb") || lower.includes("uk"))
    return "GBP";

  // Default: USD for unrecognized locales
  return "USD";
}
