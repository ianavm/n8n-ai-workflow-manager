"use client";

import { Check, X, Minus } from "lucide-react";

interface FeatureComparisonProps {
  onSelectPlan?: (slug: string) => void;
}

type FeatureValue = boolean | string | number;

interface FeatureRow {
  name: string;
  lite: FeatureValue;
  starter: FeatureValue;
  growth: FeatureValue;
  enterprise: FeatureValue;
}

const FEATURES: { category: string; features: FeatureRow[] }[] = [
  {
    category: "Limits",
    features: [
      { name: "Workflows", lite: 2, starter: 5, growth: 15, enterprise: "Unlimited" },
      { name: "Messages/mo", lite: 500, starter: "2,000", growth: "10,000", enterprise: "100,000" },
      { name: "AI Agents", lite: 0, starter: 1, growth: 5, enterprise: "Unlimited" },
      { name: "Leads/mo", lite: 50, starter: 200, growth: "1,000", enterprise: "Unlimited" },
      { name: "Departments", lite: 1, starter: 2, growth: 4, enterprise: "All" },
    ],
  },
  {
    category: "Departments",
    features: [
      { name: "Email Classifier", lite: true, starter: true, growth: true, enterprise: true },
      { name: "Lead Scraper", lite: true, starter: true, growth: true, enterprise: true },
      { name: "Accounting (QuickBooks)", lite: false, starter: true, growth: true, enterprise: true },
      { name: "Marketing Pipeline", lite: false, starter: true, growth: true, enterprise: true },
      { name: "SEO + Social", lite: false, starter: false, growth: true, enterprise: true },
      { name: "Paid Ads (Google/Meta)", lite: false, starter: false, growth: true, enterprise: true },
      { name: "Document Intake", lite: false, starter: false, growth: false, enterprise: true },
      { name: "WhatsApp Multi-Agent", lite: false, starter: false, growth: false, enterprise: true },
    ],
  },
  {
    category: "Platform",
    features: [
      { name: "Client Portal", lite: "Basic", starter: true, growth: true, enterprise: true },
      { name: "API Access", lite: false, starter: false, growth: true, enterprise: true },
      { name: "Self-Healing Ops", lite: false, starter: false, growth: true, enterprise: true },
      { name: "Intelligence Agents", lite: false, starter: false, growth: "Subset", enterprise: "All 11" },
      { name: "Custom Integrations", lite: false, starter: false, growth: false, enterprise: true },
      { name: "White-label Reports", lite: false, starter: false, growth: false, enterprise: true },
    ],
  },
  {
    category: "Support",
    features: [
      { name: "Response Time", lite: "72h", starter: "48h", growth: "24h", enterprise: "4h" },
      { name: "Email Support", lite: true, starter: true, growth: true, enterprise: true },
      { name: "Portal Support", lite: false, starter: false, growth: true, enterprise: true },
      { name: "Slack Channel", lite: false, starter: false, growth: false, enterprise: true },
      { name: "Onboarding Call", lite: false, starter: false, growth: "1 hour", enterprise: "Dedicated" },
      { name: "Quarterly Review", lite: false, starter: false, growth: false, enterprise: true },
    ],
  },
];

function renderValue(val: FeatureValue) {
  if (val === true) return <Check size={16} style={{ color: "#00D4AA" }} />;
  if (val === false) return <X size={16} style={{ color: "#4B5563" }} />;
  if (val === 0) return <Minus size={16} style={{ color: "#4B5563" }} />;
  return (
    <span style={{ color: "#fff", fontSize: "13px", fontWeight: 500 }}>
      {val}
    </span>
  );
}

export function FeatureComparison({ onSelectPlan }: FeatureComparisonProps) {
  const tiers = [
    { name: "Lite", slug: "lite", price: "R1,999" },
    { name: "Starter", slug: "starter", price: "R5,999" },
    { name: "Growth", slug: "growth", price: "R14,999", popular: true },
    { name: "Enterprise", slug: "enterprise", price: "R29,999" },
  ];

  return (
    <div
      style={{
        fontFamily: "Inter, sans-serif",
        maxWidth: "900px",
        margin: "0 auto",
      }}
    >
      {/* Header row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.5fr repeat(4, 1fr)",
          gap: "1px",
          marginBottom: "2px",
          position: "sticky",
          top: 0,
          zIndex: 10,
          background: "#0A0F1C",
          paddingBottom: "8px",
        }}
      >
        <div />
        {tiers.map((tier) => (
          <div
            key={tier.slug}
            style={{
              textAlign: "center",
              padding: "16px 8px",
            }}
          >
            <div
              style={{
                fontSize: "15px",
                fontWeight: 700,
                color: "#fff",
                marginBottom: "4px",
              }}
            >
              {tier.name}
              {tier.popular && (
                <span
                  style={{
                    display: "inline-block",
                    background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
                    color: "#fff",
                    fontSize: "9px",
                    fontWeight: 700,
                    padding: "2px 6px",
                    borderRadius: "4px",
                    marginLeft: "6px",
                    verticalAlign: "middle",
                    textTransform: "uppercase",
                  }}
                >
                  Popular
                </span>
              )}
            </div>
            <div style={{ fontSize: "13px", color: "#B0B8C8" }}>
              {tier.price}/mo
            </div>
          </div>
        ))}
      </div>

      {/* Feature categories */}
      {FEATURES.map((cat) => (
        <div key={cat.category}>
          {/* Category header */}
          <div
            style={{
              padding: "12px 16px",
              fontSize: "12px",
              fontWeight: 700,
              color: "#6C63FF",
              textTransform: "uppercase",
              letterSpacing: "1px",
              borderBottom: "1px solid rgba(108, 99, 255, 0.2)",
              marginTop: "8px",
            }}
          >
            {cat.category}
          </div>

          {/* Feature rows */}
          {cat.features.map((feature, i) => (
            <div
              key={feature.name}
              style={{
                display: "grid",
                gridTemplateColumns: "1.5fr repeat(4, 1fr)",
                gap: "1px",
                padding: "10px 0",
                borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                background:
                  i % 2 === 0
                    ? "transparent"
                    : "rgba(255, 255, 255, 0.01)",
              }}
            >
              <div
                style={{
                  padding: "0 16px",
                  fontSize: "13px",
                  color: "#B0B8C8",
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {feature.name}
              </div>
              {(["lite", "starter", "growth", "enterprise"] as const).map(
                (tier) => (
                  <div
                    key={tier}
                    style={{
                      textAlign: "center",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    {renderValue(feature[tier])}
                  </div>
                )
              )}
            </div>
          ))}
        </div>
      ))}

      {/* CTA row */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1.5fr repeat(4, 1fr)",
          gap: "8px",
          marginTop: "24px",
          paddingTop: "16px",
          borderTop: "1px solid rgba(255, 255, 255, 0.08)",
        }}
      >
        <div />
        {tiers.map((tier) => (
          <div key={tier.slug} style={{ textAlign: "center" }}>
            <button
              onClick={() => onSelectPlan?.(tier.slug)}
              style={{
                padding: "8px 16px",
                borderRadius: "8px",
                fontSize: "12px",
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "Inter, sans-serif",
                border: tier.popular ? "none" : "1px solid rgba(255, 255, 255, 0.15)",
                background: tier.popular
                  ? "linear-gradient(135deg, #6C63FF, #00D4AA)"
                  : "transparent",
                color: "#fff",
              }}
            >
              Choose {tier.name}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
