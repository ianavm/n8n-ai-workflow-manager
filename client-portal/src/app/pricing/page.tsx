"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { PricingCard } from "@/components/billing/PricingCard";
import { BillingToggle } from "@/components/billing/BillingToggle";

interface Plan {
  id: string;
  name: string;
  slug: string;
  description: string;
  price_monthly: number;
  price_yearly: number;
  limits: { workflows: number; messages: number; agents: number; leads: number };
  features: string[];
  sort_order: number;
}

export default function PricingPage() {
  const supabase = createClient();
  const [plans, setPlans] = useState<Plan[]>([]);
  const [billingInterval, setBillingInterval] = useState<"monthly" | "yearly">("monthly");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchPlans() {
      const { data } = await supabase
        .from("plans")
        .select("*")
        .eq("is_active", true)
        .order("sort_order");
      if (data) setPlans(data);
      setLoading(false);
    }
    fetchPlans();
  }, [supabase]);

  function handleSelect(slug: string) {
    window.location.href = `/portal/signup?plan=${slug}`;
  }

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
        <a
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
        </a>
        <div style={{ display: "flex", gap: "16px", alignItems: "center" }}>
          <a
            href="/portal/login"
            style={{
              color: "#B0B8C8",
              textDecoration: "none",
              fontSize: "14px",
              fontWeight: 500,
            }}
          >
            Log In
          </a>
          <a
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
          </a>
        </div>
      </nav>

      {/* Hero */}
      <div
        style={{
          textAlign: "center",
          maxWidth: "800px",
          margin: "0 auto",
          padding: "80px 24px 48px",
        }}
      >
        <h1
          style={{
            fontSize: "48px",
            fontWeight: 800,
            lineHeight: 1.15,
            margin: "0 0 20px 0",
            background: "linear-gradient(135deg, #fff 30%, #6C63FF 70%, #00D4AA)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          Simple, Transparent Pricing
        </h1>
        <p
          style={{
            fontSize: "18px",
            color: "#B0B8C8",
            lineHeight: 1.6,
            margin: "0 0 40px 0",
          }}
        >
          Deploy your AI workforce in minutes. Every plan includes a 14-day free trial
          so you can see results before you commit.
        </p>

        {/* Billing toggle */}
        <BillingToggle value={billingInterval} onChange={setBillingInterval} />
      </div>

      {/* Plans grid */}
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
            gridTemplateColumns: "repeat(3, 1fr)",
            gap: "24px",
            maxWidth: "1100px",
            margin: "0 auto",
            padding: "0 24px 80px",
          }}
        >
          {plans.map((plan) => (
            <PricingCard
              key={plan.slug}
              name={plan.name}
              slug={plan.slug}
              description={plan.description}
              priceMonthly={plan.price_monthly}
              priceYearly={plan.price_yearly}
              features={plan.features}
              limits={plan.limits}
              isPopular={plan.slug === "growth"}
              billingInterval={billingInterval}
              onSelect={(slug) => handleSelect(slug)}
              loading={false}
            />
          ))}
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
              a: "Yes! You can upgrade or downgrade your plan at any time from the billing page. Changes take effect immediately.",
            },
            {
              q: "What payment methods do you accept?",
              a: "We accept all major credit and debit cards through PayFast, South Africa's leading payment processor. EFT is also supported.",
            },
            {
              q: "Is there a setup fee?",
              a: "No. All plans are all-inclusive with no hidden fees. The price you see is the price you pay (plus 15% VAT).",
            },
            {
              q: "What does 'unlimited' mean?",
              a: "Enterprise plans include unlimited workflows and leads with no caps. Fair use applies to prevent abuse.",
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
        &copy; {new Date().getFullYear()} AnyVision Media. All rights reserved.
      </div>
    </div>
  );
}
