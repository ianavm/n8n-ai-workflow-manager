"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { PricingCard } from "@/components/billing/PricingCard";
import { BillingToggle } from "@/components/billing/BillingToggle";
import { SubscriptionStatus } from "@/components/billing/SubscriptionStatus";
import { UsageBar } from "@/components/billing/UsageBar";
import { InvoiceTable } from "@/components/billing/InvoiceTable";
import { PaymentMethodCard } from "@/components/billing/PaymentMethodCard";
import { TrialBanner } from "@/components/billing/TrialBanner";
import { AddOnCard } from "@/components/billing/AddOnCard";
import { OverageWarning } from "@/components/billing/OverageWarning";
import { toast } from "sonner";

interface Plan {
  id: string;
  name: string;
  slug: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  currency: string;
  limits: { workflows: number; messages: number; agents: number; leads: number; departments: number };
  features: string[];
  sort_order: number;
}

interface Subscription {
  subscription_id: string;
  plan_name: string;
  plan_slug: string;
  plan_description: string;
  status: "active" | "trialing" | "past_due" | "canceled" | "incomplete" | "unpaid" | "paused";
  billing_interval: "monthly" | "yearly";
  current_period_start: string;
  current_period_end: string;
  trial_end: string | null;
  cancel_at_period_end: boolean;
  limits: { workflows: number; messages: number; agents: number; leads: number; departments: number };
  features: string[];
  price_monthly: number;
  price_yearly: number;
}

interface Usage {
  messages_used: number;
  leads_used: number;
  workflows_count: number;
  agents_count: number;
}

interface Invoice {
  id: string;
  invoice_number: string;
  created_at: string;
  amount_due: number;
  vat_amount: number;
  status: "draft" | "open" | "paid" | "void" | "uncollectible";
  paid_at: string | null;
}

interface Addon {
  id: string;
  name: string;
  slug: string;
  description: string;
  price_monthly: number;
  category: string;
  features: string[];
  sort_order: number;
}

function getWarningLevel(
  used: number,
  limit: number
): "normal" | "warning" | "critical" | null {
  if (limit === -1) return null;
  if (limit === 0) return null;
  const pct = (used / limit) * 100;
  if (used >= limit) return "critical";
  if (pct >= 80) return "warning";
  return null;
}

export default function BillingPage() {
  const searchParams = useSearchParams();
  const isGated = searchParams.get("gate") === "true";
  const paymentSuccess = searchParams.get("payment") === "success";

  const supabase = createClient();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [usage, setUsage] = useState<Usage | null>(null);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [paymentMethod, setPaymentMethod] = useState<{
    card_brand?: string;
    card_last4?: string;
    card_exp_month?: number;
    card_exp_year?: number;
  } | null>(null);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [activeAddonSlugs, setActiveAddonSlugs] = useState<string[]>([]);
  const [billingInterval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [loading, setLoading] = useState(true);
  const [checkoutLoading, setCheckoutLoading] = useState<string | null>(null);
  const [showPlanPicker, setShowPlanPicker] = useState(false);
  const [addonLoading, setAddonLoading] = useState<string | null>(null);

  // Filter plans and add-ons by subscription currency
  const subscriptionCurrency = useMemo(() => {
    if (!subscription?.plan_slug) return "ZAR";
    const currentPlan = plans.find((p) => p.slug === subscription.plan_slug);
    return currentPlan?.currency || "ZAR";
  }, [subscription?.plan_slug, plans]);

  const currencyPlans = useMemo(
    () => plans.filter((p) => (p.currency || "ZAR") === subscriptionCurrency),
    [plans, subscriptionCurrency]
  );

  const currencyAddons = useMemo(() => {
    // Match add-ons by slug suffix: ZAR has no suffix, USD ends with -usd, etc.
    const suffixMap: Record<string, string> = {
      ZAR: "",
      USD: "-usd",
      EUR: "-eur",
      GBP: "-gbp",
    };
    const suffix = suffixMap[subscriptionCurrency] ?? "";
    if (!suffix) {
      // ZAR: filter out add-ons that end with -usd, -eur, -gbp
      return addons.filter(
        (a) =>
          !a.slug.endsWith("-usd") &&
          !a.slug.endsWith("-eur") &&
          !a.slug.endsWith("-gbp")
      );
    }
    return addons.filter((a) => a.slug.endsWith(suffix));
  }, [addons, subscriptionCurrency]);

  const fetchData = useCallback(async () => {
    setLoading(true);

    // Fetch plans
    const { data: plansData } = await supabase
      .from("plans")
      .select("*")
      .eq("is_active", true)
      .order("sort_order");
    if (plansData) setPlans(plansData);

    // Fetch subscription + usage via API
    const subRes = await fetch("/api/billing/subscription");
    if (subRes.ok) {
      const subData = await subRes.json();
      setSubscription(subData.subscription);
      setUsage(subData.usage);
    }

    // Fetch invoices
    const invRes = await fetch("/api/billing/invoices?limit=10");
    if (invRes.ok) {
      const invData = await invRes.json();
      setInvoices(invData.invoices || []);
    }

    // Fetch add-ons
    const addonsRes = await fetch("/api/billing/addons");
    if (addonsRes.ok) {
      const addonsData = await addonsRes.json();
      setAddons(addonsData.addons || []);
      setActiveAddonSlugs(addonsData.activeAddonSlugs || []);
    }

    // Fetch payment method
    const { data: { user } } = await supabase.auth.getUser();
    if (user) {
      const { data: client } = await supabase
        .from("clients")
        .select("id")
        .eq("auth_user_id", user.id)
        .single();
      if (client) {
        const { data: pm } = await supabase
          .from("payment_methods")
          .select("*")
          .eq("client_id", client.id)
          .eq("is_default", true)
          .maybeSingle();
        if (pm) setPaymentMethod(pm);
      }
    }

    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (paymentSuccess) {
      toast.success("Payment successful! Welcome to AnyVision.");
      setTimeout(fetchData, 2000);
    }
  }, [paymentSuccess, fetchData]);

  async function handleSelectPlan(planSlug: string, interval: "monthly" | "yearly") {
    setCheckoutLoading(planSlug);
    try {
      // PayFast Checkout — submit form to PayFast's hosted payment page
      const res = await fetch("/api/billing/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planSlug, billingInterval: interval }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.error || "Failed to create checkout");
        return;
      }
      const form = document.createElement("form");
      form.method = "POST";
      form.action = data.paymentUrl;
      for (const [key, value] of Object.entries(data.paymentData)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = key;
        input.value = value as string;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } catch {
      toast.error("Something went wrong. Please try again.");
    } finally {
      setCheckoutLoading(null);
    }
  }

  async function handleCancel() {
    if (!confirm("Are you sure you want to cancel your subscription? You'll retain access until the end of your current billing period.")) return;
    try {
      const res = await fetch("/api/billing/cancel", { method: "POST" });
      if (res.ok) {
        toast.success("Subscription will be canceled at the end of your billing period.");
        fetchData();
      } else {
        toast.error("Failed to cancel subscription.");
      }
    } catch {
      toast.error("Something went wrong.");
    }
  }

  async function handleChangePlan(planSlug: string, interval: "monthly" | "yearly") {
    setCheckoutLoading(planSlug);
    try {
      const res = await fetch("/api/billing/change-plan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planSlug, billingInterval: interval }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.error || "Failed to change plan");
        return;
      }
      const form = document.createElement("form");
      form.method = "POST";
      form.action = data.paymentUrl;
      for (const [key, value] of Object.entries(data.paymentData)) {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = key;
        input.value = value as string;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } catch {
      toast.error("Something went wrong.");
    } finally {
      setCheckoutLoading(null);
    }
  }

  async function handleAddonAction(addonSlug: string, action: "purchase" | "cancel") {
    setAddonLoading(addonSlug);
    try {
      const res = await fetch("/api/billing/addons", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ addonSlug, action }),
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(data.error || `Failed to ${action} add-on`);
        return;
      }

      // Handle PayFast checkout redirect for purchase
      if (action === "purchase" && data.paymentData) {
        const form = document.createElement("form");
        form.method = "POST";
        form.action = data.paymentUrl;
        for (const [key, value] of Object.entries(data.paymentData)) {
          const input = document.createElement("input");
          input.type = "hidden";
          input.name = key;
          input.value = value as string;
          form.appendChild(input);
        }
        document.body.appendChild(form);
        form.submit();
        return;
      }

      toast.success(data.message);
      fetchData();
    } catch {
      toast.error("Something went wrong.");
    } finally {
      setAddonLoading(null);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #6C63FF",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  const hasSubscription = !!subscription;
  const isTrialing = subscription?.status === "trialing";
  const isPastDue = subscription?.status === "past_due";
  const isCanceled = !hasSubscription || subscription?.status === "canceled";
  const showPricing = isGated || isCanceled || showPlanPicker;

  // Build overage warnings
  const warnings: Array<{
    feature: string;
    used: number;
    limit: number;
    overageCount: number;
    level: "warning" | "critical";
  }> = [];

  if (usage && subscription && !isCanceled) {
    const checks = [
      { feature: "messages", used: usage.messages_used, limit: subscription.limits.messages },
      { feature: "leads", used: usage.leads_used, limit: subscription.limits.leads },
      { feature: "workflows", used: usage.workflows_count, limit: subscription.limits.workflows },
      { feature: "agents", used: usage.agents_count, limit: subscription.limits.agents },
    ];

    for (const check of checks) {
      const level = getWarningLevel(check.used, check.limit);
      if (level === "warning" || level === "critical") {
        warnings.push({
          feature: check.feature,
          used: check.used,
          limit: check.limit,
          overageCount: Math.max(0, check.used - check.limit),
          level,
        });
      }
    }
  }

  return (
    <div>
      {/* Page header */}
      <div
        style={{
          marginBottom: "28px",
          animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        }}
      >
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>
          {showPricing && !hasSubscription ? "Choose Your Plan" : "Billing & Subscription"}
        </h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          {showPricing && !hasSubscription
            ? "Select a plan to get started with your AI workforce."
            : "Manage your subscription, add-ons, and usage."}
        </p>
      </div>

      {/* Trial banner */}
      {isTrialing && subscription.trial_end && (
        <div style={{ marginBottom: "28px" }}>
          <TrialBanner
            trialEnd={subscription.trial_end}
            planName={subscription.plan_name}
            amount={
              subscription.billing_interval === "monthly"
                ? subscription.price_monthly
                : subscription.price_yearly
            }
          />
        </div>
      )}

      {/* Past due warning */}
      {isPastDue && (
        <div
          style={{
            marginBottom: "28px",
            padding: "16px 20px",
            borderRadius: "12px",
            background: "rgba(255,109,90,0.08)",
            border: "1px solid rgba(255,109,90,0.2)",
            display: "flex",
            alignItems: "center",
            gap: "12px",
            fontSize: "14px",
            color: "#FF6D5A",
          }}
        >
          <span style={{ fontWeight: 600 }}>Payment Failed</span>
          <span style={{ color: "#B0B8C8" }}>
            Your last payment was unsuccessful. Please update your payment method to avoid service interruption.
          </span>
        </div>
      )}

      {/* Overage warnings */}
      {warnings.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", marginBottom: "28px" }}>
          {warnings.map((w) => (
            <OverageWarning
              key={w.feature}
              feature={w.feature}
              used={w.used}
              limit={w.limit}
              overageCount={w.overageCount}
              level={w.level}
              onUpgrade={() => setShowPlanPicker(true)}
            />
          ))}
        </div>
      )}

      {/* Subscription status + usage (when subscribed) */}
      {hasSubscription && subscription.status !== "canceled" && !showPricing && (
        <div style={{ display: "flex", flexDirection: "column", gap: "28px", marginBottom: "28px" }}>
          <SubscriptionStatus
            planName={subscription.plan_name}
            planSlug={subscription.plan_slug}
            status={subscription.status}
            billingInterval={subscription.billing_interval}
            periodEnd={subscription.current_period_end}
            trialEnd={subscription.trial_end}
            cancelAtPeriodEnd={subscription.cancel_at_period_end}
            priceMonthly={subscription.price_monthly}
            priceYearly={subscription.price_yearly}
            onChangePlan={() => setShowPlanPicker(true)}
            onCancel={handleCancel}
            onReactivate={() => {
              fetch("/api/billing/cancel", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ reactivate: true }),
              }).then(() => fetchData());
            }}
          />

          {/* Usage bars */}
          {usage && (
            <div className="glass-card" style={{ padding: "28px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "20px" }}>
                Usage This Period
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
                <UsageBar label="Messages" used={usage.messages_used} limit={subscription.limits.messages} unit="messages" />
                <UsageBar label="Leads" used={usage.leads_used} limit={subscription.limits.leads} unit="leads" />
                <UsageBar label="Workflows" used={usage.workflows_count} limit={subscription.limits.workflows} unit="workflows" />
                <UsageBar label="AI Agents" used={usage.agents_count} limit={subscription.limits.agents} unit="agents" />
              </div>
            </div>
          )}

          {/* Active add-ons */}
          {activeAddonSlugs.length > 0 && (
            <div className="glass-card" style={{ padding: "28px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "20px" }}>
                Active Add-Ons
              </h3>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
                {addons
                  .filter((a) => activeAddonSlugs.includes(a.slug))
                  .map((addon) => (
                    <AddOnCard
                      key={addon.slug}
                      name={addon.name}
                      slug={addon.slug}
                      description={addon.description}
                      priceMonthly={addon.price_monthly}
                      features={addon.features}
                      category={addon.category}
                      isActive={true}
                      onAction={handleAddonAction}
                      loading={addonLoading === addon.slug}
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Add-on marketplace */}
          {currencyAddons.filter((a) => !activeAddonSlugs.includes(a.slug)).length > 0 && (
            <div className="glass-card" style={{ padding: "28px" }}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "4px" }}>
                Available Add-Ons
              </h3>
              <p style={{ fontSize: "13px", color: "#6B7280", margin: "0 0 20px 0" }}>
                Extend your plan with modular capabilities
              </p>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "16px" }}>
                {currencyAddons
                  .filter((a) => !activeAddonSlugs.includes(a.slug))
                  .map((addon) => (
                    <AddOnCard
                      key={addon.slug}
                      name={addon.name}
                      slug={addon.slug}
                      description={addon.description}
                      priceMonthly={addon.price_monthly}
                      features={addon.features}
                      category={addon.category}
                      isActive={false}
                      onAction={handleAddonAction}
                      loading={addonLoading === addon.slug}
                    />
                  ))}
              </div>
            </div>
          )}

          {/* Payment method */}
          <PaymentMethodCard
            cardBrand={paymentMethod?.card_brand}
            cardLast4={paymentMethod?.card_last4}
            cardExpMonth={paymentMethod?.card_exp_month}
            cardExpYear={paymentMethod?.card_exp_year}
            onUpdate={() => {
              toast.info("To update your payment method, please contact support.");
            }}
          />
        </div>
      )}

      {/* Pricing cards (when gated, canceled, or changing plan) */}
      {showPricing && (
        <div style={{ marginBottom: "28px" }}>
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "32px" }}>
            <BillingToggle value={billingInterval} onChange={setBillingInterval} />
          </div>

          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${Math.min(currencyPlans.length, 4)}, 1fr)`,
              gap: "20px",
              marginBottom: "28px",
            }}
          >
            {currencyPlans.map((plan) => (
              <PricingCard
                key={plan.slug}
                name={plan.name}
                slug={plan.slug}
                description={plan.description}
                priceMonthly={plan.price_monthly}
                priceYearly={plan.price_yearly}
                features={plan.features}
                limits={plan.limits}
                currency={plan.currency}
                isPopular={plan.slug.startsWith("growth")}
                isCurrentPlan={subscription?.plan_slug === plan.slug}
                billingInterval={billingInterval}
                onSelect={hasSubscription ? handleChangePlan : handleSelectPlan}
                loading={checkoutLoading === plan.slug}
              />
            ))}
          </div>

          {showPlanPicker && hasSubscription && (
            <div style={{ textAlign: "center" }}>
              <button
                onClick={() => setShowPlanPicker(false)}
                className="btn-outline"
                style={{ fontSize: "13px" }}
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      )}

      {/* Invoice history */}
      {hasSubscription && subscription.status !== "canceled" && (
        <InvoiceTable invoices={invoices} loading={loading} />
      )}
    </div>
  );
}
