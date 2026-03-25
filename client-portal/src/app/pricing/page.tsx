"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { PricingCard } from "@/components/billing/PricingCard";
import { BillingToggle } from "@/components/billing/BillingToggle";
import { CurrencySelector } from "@/components/billing/CurrencySelector";
import { AddOnCard } from "@/components/billing/AddOnCard";
import { FeatureComparison } from "@/components/billing/FeatureComparison";
import { ROICalculator } from "@/components/billing/ROICalculator";

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

export default function PricingPage() {
  const router = useRouter();
  const supabase = createClient();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [addons, setAddons] = useState<Addon[]>([]);
  const [billingInterval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [currency, setCurrency] = useState<string>("ZAR");
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState<"plans" | "comparison" | "addons" | "calculator">("plans");

  // Currency locked to ZAR (PayFast only). Stripe multi-currency to be enabled later.
  // Auto-detect code preserved for when Stripe is activated:
  // useEffect(() => {
  //   const locale = navigator.language || "en-ZA";
  //   const lower = locale.toLowerCase();
  //   if (lower.includes("gb") || lower.includes("uk")) setCurrency("GBP");
  //   else if (["de","fr","es","it","nl","pt"].some(c => lower.includes(c))) setCurrency("EUR");
  //   else if (lower.includes("us") || lower.includes("en-us")) setCurrency("USD");
  // }, []);

  useEffect(() => {
    async function fetchData() {
      const [plansRes, addonsRes] = await Promise.all([
        supabase.from("plans").select("*").eq("is_active", true).order("sort_order"),
        supabase.from("addons").select("*").eq("is_active", true).order("sort_order"),
      ]);
      if (plansRes.data) setPlans(plansRes.data);
      if (addonsRes.data) setAddons(addonsRes.data);
      setLoading(false);
    }
    fetchData();
  }, [supabase]);

  function handleSelectPlan(slug: string) {
    router.push(`/portal/signup?plan=${slug}&currency=${currency}`);
  }

  // Filter plans and addons by selected currency
  const filteredPlans = plans.filter((p) => (p.currency || "ZAR") === currency);
  const filteredAddons = addons.filter((a) => {
    // Match add-ons by slug suffix (e.g., "seo-growth-pack-usd" for USD)
    const suffixMap: Record<string, string> = { ZAR: "", USD: "-usd", EUR: "-eur", GBP: "-gbp" };
    const suffix = suffixMap[currency] || "";
    if (currency === "ZAR") return !a.slug.endsWith("-usd") && !a.slug.endsWith("-eur") && !a.slug.endsWith("-gbp");
    return a.slug.endsWith(suffix);
  });

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "#0A0F1C",
        color: "#fff",
        fontFamily: "Inter, system-ui, sans-serif",
      }}
    >
      {/* Nav */}
      <nav
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "20px 40px",
          maxWidth: "1200px",
          margin: "0 auto",
        }}
      >
        <Link
          href="/"
          style={{
            fontSize: "20px",
            fontWeight: 700,
            color: "#fff",
            textDecoration: "none",
            display: "flex",
            alignItems: "center",
            gap: "8px",
          }}
        >
          <span
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "16px",
              fontWeight: 800,
            }}
          >
            A
          </span>
          AnyVision
        </Link>
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <Link
            href="/portal/login"
            style={{
              color: "#B0B8C8",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: 500,
            }}
          >
            Log In
          </Link>
          <Link
            href="/portal/signup"
            style={{
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              color: "#fff",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: 600,
              padding: "10px 24px",
              borderRadius: "12px",
            }}
          >
            Get Started
          </Link>
        </div>
      </nav>

      {/* Hero */}
      <div
        style={{
          textAlign: "center",
          maxWidth: "800px",
          margin: "0 auto",
          padding: "60px 24px 32px",
        }}
      >
        <h1
          style={{
            fontSize: "48px",
            fontWeight: 800,
            lineHeight: 1.15,
            margin: "0 0 16px 0",
            background: "linear-gradient(135deg, #fff 30%, #6C63FF 70%, #00D4AA)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          Your AI Workforce, Priced for Value
        </h1>
        <p
          style={{
            fontSize: "18px",
            color: "#B0B8C8",
            lineHeight: 1.6,
            margin: "0 0 8px 0",
          }}
        >
          Replace entire departments with AI automation that works 24/7.
          Every plan includes a 14-day free trial.
        </p>
        <p
          style={{
            fontSize: "14px",
            color: "#6B7280",
            margin: "0 0 32px 0",
          }}
        >
          No credit card required to start. Cancel anytime.
        </p>

        {/* Currency selector — hidden until Stripe is activated */}
        {/* <div style={{ marginBottom: "16px" }}>
          <CurrencySelector value={currency} onChange={setCurrency} />
        </div> */}

        {/* Billing toggle */}
        <BillingToggle value={billingInterval} onChange={setBillingInterval} />
      </div>

      {/* Section tabs */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "4px",
          marginBottom: "40px",
          padding: "0 24px",
        }}
      >
        {[
          { key: "plans", label: "Plans" },
          { key: "comparison", label: "Compare Features" },
          { key: "addons", label: "Add-Ons" },
          { key: "calculator", label: "ROI Calculator" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveSection(tab.key as typeof activeSection)}
            style={{
              padding: "8px 20px",
              borderRadius: "8px",
              fontSize: "13px",
              fontWeight: 600,
              fontFamily: "Inter, sans-serif",
              cursor: "pointer",
              border: "none",
              background:
                activeSection === tab.key
                  ? "rgba(108, 99, 255, 0.15)"
                  : "transparent",
              color:
                activeSection === tab.key ? "#6C63FF" : "#6B7280",
              transition: "all 0.2s ease",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Plans grid */}
      {activeSection === "plans" && (
        <>
          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "60px 0" }}>
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
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "20px",
                maxWidth: "1200px",
                margin: "0 auto",
                padding: "0 24px 40px",
              }}
            >
              {filteredPlans.map((plan) => (
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
                  billingInterval={billingInterval}
                  onSelect={(slug) => handleSelectPlan(slug)}
                  loading={false}
                />
              ))}
            </div>
          )}

          {/* Enterprise CTA */}
          <div
            style={{
              textAlign: "center",
              padding: "20px 24px 60px",
            }}
          >
            <p
              style={{
                fontSize: "15px",
                color: "#B0B8C8",
                margin: "0 0 12px 0",
              }}
            >
              Need a custom solution for your enterprise?
            </p>
            <a
              href="https://calendly.com/ian-anyvisionmedia/strategy"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "8px",
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.15)",
                color: "#fff",
                textDecoration: "none",
                fontSize: "14px",
                fontWeight: 600,
                padding: "12px 28px",
                borderRadius: "12px",
                transition: "border-color 0.2s ease",
              }}
            >
              Book a Strategy Call
            </a>
          </div>

          {/* Value props */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
              gap: "20px",
              maxWidth: "1000px",
              margin: "0 auto",
              padding: "0 24px 60px",
            }}
          >
            {[
              { stat: "80+", label: "AI Workflows" },
              { stat: "24/7", label: "Always Running" },
              { stat: "11", label: "Departments" },
              { stat: "3x", label: "Average ROI" },
            ].map((item) => (
              <div key={item.label} style={{ textAlign: "center" }}>
                <div
                  style={{
                    fontSize: "32px",
                    fontWeight: 800,
                    background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
                    WebkitBackgroundClip: "text",
                    WebkitTextFillColor: "transparent",
                    marginBottom: "4px",
                  }}
                >
                  {item.stat}
                </div>
                <div style={{ fontSize: "13px", color: "#6B7280" }}>
                  {item.label}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Feature comparison */}
      {activeSection === "comparison" && (
        <div style={{ padding: "0 24px 80px" }}>
          <FeatureComparison onSelectPlan={handleSelectPlan} />
        </div>
      )}

      {/* Add-ons section */}
      {activeSection === "addons" && (
        <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px 80px" }}>
          <div style={{ textAlign: "center", marginBottom: "32px" }}>
            <h2
              style={{
                fontSize: "28px",
                fontWeight: 700,
                margin: "0 0 8px 0",
              }}
            >
              Power Up with Add-Ons
            </h2>
            <p style={{ fontSize: "15px", color: "#B0B8C8", margin: 0 }}>
              Extend any plan with modular capabilities. Add or remove anytime.
            </p>
          </div>

          {loading ? (
            <div style={{ display: "flex", justifyContent: "center", padding: "40px 0" }}>
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
          ) : (
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))",
                gap: "16px",
              }}
            >
              {filteredAddons.map((addon) => (
                <AddOnCard
                  key={addon.slug}
                  name={addon.name}
                  slug={addon.slug}
                  description={addon.description}
                  priceMonthly={addon.price_monthly}
                  features={addon.features}
                  category={addon.category}
                  onAction={(slug) =>
                    router.push(`/portal/signup?addon=${slug}&currency=${currency}`)
                  }
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* ROI Calculator */}
      {activeSection === "calculator" && (
        <div style={{ padding: "0 24px 80px" }}>
          <ROICalculator onSelectPlan={handleSelectPlan} />
        </div>
      )}

      {/* FAQ */}
      <div
        style={{
          maxWidth: "800px",
          margin: "0 auto",
          padding: "0 24px 100px",
        }}
      >
        <h2
          style={{
            fontSize: "28px",
            fontWeight: 700,
            textAlign: "center",
            marginBottom: "40px",
          }}
        >
          Frequently Asked Questions
        </h2>
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {[
            {
              q: "What happens after my 14-day trial?",
              a: "Your card will be charged at the end of the trial. You can cancel anytime during the trial with zero charges.",
            },
            {
              q: "Can I switch plans later?",
              a: "Yes! You can upgrade or downgrade your plan at any time from the billing page. Changes take effect immediately with pro-rated billing.",
            },
            {
              q: "What payment methods do you accept?",
              a: "We accept all major credit and debit cards. South African clients pay via PayFast (EFT also supported). International clients (USD/EUR/GBP) pay securely via Stripe, supporting cards from 135+ countries.",
            },
            {
              q: "What happens if I exceed my plan limits?",
              a: "You can use up to 2x your plan limit in a soft overage zone. Overage charges (R0.50/message, R2/lead) are billed at the end of your billing period. You'll get alerts at 80% and 95% usage.",
            },
            {
              q: "Can I add and remove add-ons anytime?",
              a: "Yes. Add-ons are billed monthly and can be activated or canceled from your billing page at any time. No long-term commitment.",
            },
            {
              q: "Is there a setup fee?",
              a: "Standard onboarding is free on all plans. Guided onboarding (R2,999) is free with Growth and Enterprise plans. Custom workflow builds and integrations are quoted separately.",
            },
            {
              q: "What does 'unlimited' mean?",
              a: "Enterprise plans include unlimited workflows, AI agents, and leads with no caps. Fair use applies to prevent abuse.",
            },
            {
              q: "Do you offer annual billing?",
              a: "Yes! Save 17% (equivalent to 2 months free) when you choose annual billing on any plan.",
            },
          ].map((faq, i) => (
            <div
              key={i}
              style={{
                background: "rgba(255, 255, 255, 0.05)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "14px",
                padding: "20px 24px",
              }}
            >
              <h3
                style={{
                  fontSize: "15px",
                  fontWeight: 600,
                  color: "#fff",
                  margin: "0 0 8px 0",
                }}
              >
                {faq.q}
              </h3>
              <p
                style={{
                  fontSize: "14px",
                  color: "#B0B8C8",
                  margin: 0,
                  lineHeight: 1.6,
                }}
              >
                {faq.a}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid rgba(255, 255, 255, 0.06)",
          padding: "24px 40px",
          textAlign: "center",
          fontSize: "13px",
          color: "#6B7280",
        }}
      >
        {currency === "ZAR" ? "All prices exclude 15% VAT. " : "All prices in " + currency + ". "}
        &copy; {new Date().getFullYear()} AnyVision Media. All rights reserved.
      </div>
    </div>
  );
}
