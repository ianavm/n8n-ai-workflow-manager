"use client";

import { CreditCard } from "lucide-react";

interface PaymentMethodCardProps {
  cardBrand?: string;
  cardLast4?: string;
  cardExpMonth?: number;
  cardExpYear?: number;
  onUpdate: () => void;
}

const brandColors: Record<string, string> = {
  visa: "#1A1F71",
  mastercard: "#EB001B",
  amex: "#006FCF",
};

function BrandBadge({ brand }: { brand: string }) {
  const normalized = brand.toLowerCase();
  const displayName =
    normalized === "visa"
      ? "VISA"
      : normalized === "mastercard"
        ? "MC"
        : normalized === "amex"
          ? "AMEX"
          : brand.toUpperCase();

  return (
    <span
      style={{
        background: brandColors[normalized] || "rgba(108, 99, 255, 0.2)",
        color: "#fff",
        fontSize: "11px",
        fontWeight: 800,
        padding: "6px 12px",
        borderRadius: "6px",
        letterSpacing: "1px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {displayName}
    </span>
  );
}

export function PaymentMethodCard({
  cardBrand,
  cardLast4,
  cardExpMonth,
  cardExpYear,
  onUpdate,
}: PaymentMethodCardProps) {
  const hasCard = cardLast4 && cardBrand;

  return (
    <div
      style={{
        background: "rgba(255, 255, 255, 0.05)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "16px",
        padding: "20px 24px",
        fontFamily: "Inter, sans-serif",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: "16px",
        flexWrap: "wrap",
      }}
    >
      {hasCard ? (
        <>
          {/* Left: Brand badge */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "16px",
            }}
          >
            <BrandBadge brand={cardBrand} />

            {/* Middle: Card details */}
            <div>
              <p
                style={{
                  margin: "0 0 4px 0",
                  fontSize: "14px",
                  color: "#fff",
                  fontWeight: 500,
                  letterSpacing: "1.5px",
                }}
              >
                {"•••• •••• •••• "}
                {cardLast4}
              </p>
              <p
                style={{
                  margin: 0,
                  fontSize: "12px",
                  color: "#6B7280",
                }}
              >
                Expires{" "}
                {String(cardExpMonth).padStart(2, "0")}/{cardExpYear}
              </p>
            </div>
          </div>

          {/* Right: Update button */}
          <button
            className="btn-outline"
            onClick={onUpdate}
            style={{
              padding: "8px 16px",
              borderRadius: "10px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
            }}
          >
            Update
          </button>
        </>
      ) : (
        <>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "12px",
            }}
          >
            <CreditCard size={20} style={{ color: "#6B7280" }} />
            <span style={{ fontSize: "14px", color: "#6B7280" }}>
              No payment method on file
            </span>
          </div>

          <button
            className="btn-gradient"
            onClick={onUpdate}
            style={{
              padding: "10px 20px",
              borderRadius: "12px",
              fontSize: "13px",
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
            }}
          >
            Add Payment Method
          </button>
        </>
      )}
    </div>
  );
}
