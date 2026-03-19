"use client";

import { Check } from "lucide-react";

interface PricingCardProps {
  name: string;
  slug: string;
  description: string;
  priceMonthly: number;
  priceYearly: number;
  features: string[];
  limits: Record<string, number>;
  currency?: string;
  isPopular?: boolean;
  isCurrentPlan?: boolean;
  billingInterval: "monthly" | "yearly";
  onSelect: (slug: string, interval: "monthly" | "yearly") => void;
  loading?: boolean;
}

const CURRENCY_SYMBOLS: Record<string, { symbol: string; locale: string }> = {
  ZAR: { symbol: "R", locale: "en-ZA" },
  USD: { symbol: "$", locale: "en-US" },
  EUR: { symbol: "\u20AC", locale: "de-DE" },
  GBP: { symbol: "\u00A3", locale: "en-GB" },
};

function formatPrice(cents: number, currency: string = "ZAR"): string {
  const config = CURRENCY_SYMBOLS[currency] || CURRENCY_SYMBOLS.ZAR;
  const amount = cents / 100;
  const formatted = amount.toLocaleString(config.locale, {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return `${config.symbol}${formatted}`;
}

export function PricingCard({
  name,
  slug,
  description,
  priceMonthly,
  priceYearly,
  features,
  currency = "ZAR",
  isPopular = false,
  isCurrentPlan = false,
  billingInterval,
  onSelect,
  loading = false,
}: PricingCardProps) {
  const price = billingInterval === "monthly" ? priceMonthly : priceYearly;
  const suffix = billingInterval === "monthly" ? "/mo" : "/yr";

  return (
    <div
      style={{
        position: "relative",
        borderRadius: "20px",
        padding: isPopular ? "2px" : "0",
        background: isPopular
          ? "linear-gradient(135deg, #6C63FF, #00D4AA)"
          : "transparent",
        transition: "transform 0.3s ease, box-shadow 0.3s ease",
        cursor: "default",
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = "translateY(-8px)";
        e.currentTarget.style.boxShadow =
          "0 20px 40px rgba(108, 99, 255, 0.25)";
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = "translateY(0)";
        e.currentTarget.style.boxShadow = "none";
      }}
    >
      <div
        style={{
          background: "rgba(255, 255, 255, 0.05)",
          border: isPopular ? "none" : "1px solid rgba(255, 255, 255, 0.08)",
          borderRadius: isPopular ? "18px" : "20px",
          padding: "32px 28px",
          display: "flex",
          flexDirection: "column",
          height: "100%",
          position: "relative",
          overflow: "hidden",
        }}
      >
        {/* Popular badge */}
        {isPopular && (
          <div
            style={{
              position: "absolute",
              top: "16px",
              right: "16px",
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              color: "#fff",
              fontSize: "11px",
              fontWeight: 700,
              padding: "4px 12px",
              borderRadius: "20px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Most Popular
          </div>
        )}

        {/* Plan name */}
        <h3
          style={{
            fontSize: "20px",
            fontWeight: 700,
            color: "#fff",
            margin: "0 0 8px 0",
            fontFamily: "Inter, sans-serif",
          }}
        >
          {name}
        </h3>

        {/* Description */}
        <p
          style={{
            fontSize: "14px",
            color: "#B0B8C8",
            margin: "0 0 24px 0",
            lineHeight: 1.5,
            fontFamily: "Inter, sans-serif",
          }}
        >
          {description}
        </p>

        {/* Price */}
        <div style={{ marginBottom: "24px" }}>
          <span
            style={{
              fontSize: "36px",
              fontWeight: 700,
              color: "#fff",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {formatPrice(price, currency)}
          </span>
          <span
            style={{
              fontSize: "14px",
              color: "#6B7280",
              fontFamily: "Inter, sans-serif",
            }}
          >
            {suffix}
          </span>
        </div>

        {/* Annual savings badge */}
        {billingInterval === "yearly" && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              background: "rgba(0, 212, 170, 0.1)",
              color: "#00D4AA",
              fontSize: "12px",
              fontWeight: 600,
              padding: "4px 10px",
              borderRadius: "8px",
              marginBottom: "24px",
              width: "fit-content",
              fontFamily: "Inter, sans-serif",
            }}
          >
            Save 17%
          </div>
        )}

        {/* Features */}
        <ul
          style={{
            listStyle: "none",
            padding: 0,
            margin: "0 0 32px 0",
            flex: 1,
          }}
        >
          {features.map((feature, i) => (
            <li
              key={i}
              style={{
                display: "flex",
                alignItems: "flex-start",
                gap: "10px",
                marginBottom: "12px",
                fontSize: "14px",
                color: "#B0B8C8",
                fontFamily: "Inter, sans-serif",
                lineHeight: 1.4,
              }}
            >
              <Check
                size={16}
                style={{
                  color: "#00D4AA",
                  flexShrink: 0,
                  marginTop: "2px",
                }}
              />
              {feature}
            </li>
          ))}
        </ul>

        {/* CTA Button */}
        <button
          className={isPopular ? "btn-gradient" : "btn-outline"}
          disabled={isCurrentPlan || loading}
          onClick={() => onSelect(slug, billingInterval)}
          style={{
            width: "100%",
            padding: "14px 24px",
            borderRadius: "12px",
            fontSize: "15px",
            fontWeight: 600,
            fontFamily: "Inter, sans-serif",
            cursor: isCurrentPlan ? "default" : "pointer",
            opacity: isCurrentPlan ? 0.5 : 1,
            transition: "opacity 0.2s ease",
          }}
        >
          {loading
            ? "Processing..."
            : isCurrentPlan
              ? "Current Plan"
              : "Get Started"}
        </button>
      </div>
    </div>
  );
}
