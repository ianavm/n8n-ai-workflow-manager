"use client";

import { Check } from "lucide-react";

interface AddOnCardProps {
  name: string;
  slug: string;
  description: string;
  priceMonthly: number;
  features: string[];
  category: string;
  isActive?: boolean;
  onAction: (slug: string, action: "purchase" | "cancel") => void;
  loading?: boolean;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

const CATEGORY_COLORS: Record<string, string> = {
  department: "#6C63FF",
  resources: "#00D4AA",
  support: "#FF6D5A",
};

export function AddOnCard({
  name,
  slug,
  description,
  priceMonthly,
  features,
  category,
  isActive = false,
  onAction,
  loading = false,
}: AddOnCardProps) {
  const categoryColor = CATEGORY_COLORS[category] || "#6C63FF";

  return (
    <div
      style={{
        background: isActive
          ? "rgba(0, 212, 170, 0.05)"
          : "rgba(255, 255, 255, 0.03)",
        border: isActive
          ? "1px solid rgba(0, 212, 170, 0.3)"
          : "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "16px",
        padding: "24px",
        display: "flex",
        flexDirection: "column",
        transition: "border-color 0.2s ease, background 0.2s ease",
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.borderColor = "rgba(108, 99, 255, 0.3)";
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.05)";
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.borderColor = "rgba(255, 255, 255, 0.08)";
          e.currentTarget.style.background = "rgba(255, 255, 255, 0.03)";
        }
      }}
    >
      {/* Category badge */}
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          width: "fit-content",
          background: `${categoryColor}20`,
          color: categoryColor,
          fontSize: "11px",
          fontWeight: 600,
          padding: "3px 10px",
          borderRadius: "8px",
          textTransform: "uppercase",
          letterSpacing: "0.5px",
          marginBottom: "12px",
          fontFamily: "Inter, sans-serif",
        }}
      >
        {category}
      </div>

      {/* Name */}
      <h4
        style={{
          fontSize: "16px",
          fontWeight: 700,
          color: "#fff",
          margin: "0 0 6px 0",
          fontFamily: "Inter, sans-serif",
        }}
      >
        {name}
      </h4>

      {/* Description */}
      <p
        style={{
          fontSize: "13px",
          color: "#B0B8C8",
          margin: "0 0 16px 0",
          lineHeight: 1.5,
          fontFamily: "Inter, sans-serif",
        }}
      >
        {description}
      </p>

      {/* Price */}
      <div style={{ marginBottom: "16px" }}>
        <span
          style={{
            fontSize: "24px",
            fontWeight: 700,
            color: "#fff",
            fontFamily: "Inter, sans-serif",
          }}
        >
          {formatZAR(priceMonthly)}
        </span>
        <span
          style={{
            fontSize: "13px",
            color: "#6B7280",
            fontFamily: "Inter, sans-serif",
          }}
        >
          /mo
        </span>
      </div>

      {/* Features */}
      <ul
        style={{
          listStyle: "none",
          padding: 0,
          margin: "0 0 20px 0",
          flex: 1,
        }}
      >
        {features.slice(0, 4).map((feature, i) => (
          <li
            key={i}
            style={{
              display: "flex",
              alignItems: "flex-start",
              gap: "8px",
              marginBottom: "8px",
              fontSize: "13px",
              color: "#B0B8C8",
              fontFamily: "Inter, sans-serif",
              lineHeight: 1.4,
            }}
          >
            <Check
              size={14}
              style={{
                color: "#00D4AA",
                flexShrink: 0,
                marginTop: "2px",
              }}
            />
            {feature}
          </li>
        ))}
        {features.length > 4 && (
          <li
            style={{
              fontSize: "12px",
              color: "#6B7280",
              marginTop: "4px",
              fontFamily: "Inter, sans-serif",
            }}
          >
            +{features.length - 4} more features
          </li>
        )}
      </ul>

      {/* Action button */}
      <button
        disabled={loading}
        onClick={() => onAction(slug, isActive ? "cancel" : "purchase")}
        style={{
          width: "100%",
          padding: "10px 20px",
          borderRadius: "10px",
          fontSize: "13px",
          fontWeight: 600,
          fontFamily: "Inter, sans-serif",
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.6 : 1,
          transition: "opacity 0.2s ease",
          border: isActive ? "1px solid rgba(255, 109, 90, 0.5)" : "none",
          background: isActive
            ? "transparent"
            : "linear-gradient(135deg, #6C63FF, #00D4AA)",
          color: isActive ? "#FF6D5A" : "#fff",
        }}
      >
        {loading ? "Processing..." : isActive ? "Remove Add-On" : "Add to Plan"}
      </button>
    </div>
  );
}
