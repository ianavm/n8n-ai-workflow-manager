"use client";

import { useState } from "react";

interface ROICalculatorProps {
  onSelectPlan?: (slug: string) => void;
}

// Estimated hours saved per department per month
const DEPARTMENT_HOURS: Record<string, { name: string; hours: number; salary: number }> = {
  accounting: { name: "Accounting", hours: 80, salary: 25000 },
  marketing: { name: "Marketing", hours: 60, salary: 22000 },
  seo: { name: "SEO & Social", hours: 100, salary: 28000 },
  ads: { name: "Paid Advertising", hours: 50, salary: 30000 },
  leads: { name: "Lead Generation", hours: 40, salary: 20000 },
  support: { name: "Customer Support", hours: 70, salary: 18000 },
};

function formatZAR(amount: number): string {
  return `R${amount.toLocaleString("en-ZA")}`;
}

export function ROICalculator({ onSelectPlan }: ROICalculatorProps) {
  const [selected, setSelected] = useState<string[]>(["accounting", "marketing"]);

  const totalHours = selected.reduce(
    (sum, key) => sum + (DEPARTMENT_HOURS[key]?.hours ?? 0),
    0
  );
  const totalSalary = selected.reduce(
    (sum, key) => sum + (DEPARTMENT_HOURS[key]?.salary ?? 0),
    0
  );

  // Suggest a plan based on department count
  const suggestedPlan =
    selected.length <= 1
      ? { name: "Lite", slug: "lite", price: 1999 }
      : selected.length <= 2
        ? { name: "Starter", slug: "starter", price: 5999 }
        : selected.length <= 4
          ? { name: "Growth", slug: "growth", price: 14999 }
          : { name: "Enterprise", slug: "enterprise", price: 29999 };

  const monthlySavings = totalSalary - suggestedPlan.price;
  const roiMultiple = suggestedPlan.price > 0
    ? Math.round(totalSalary / suggestedPlan.price)
    : 0;

  function toggleDept(key: string) {
    setSelected((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  return (
    <div
      style={{
        background: "rgba(255, 255, 255, 0.03)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "20px",
        padding: "32px",
        maxWidth: "700px",
        margin: "0 auto",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <h3
        style={{
          fontSize: "22px",
          fontWeight: 700,
          color: "#fff",
          margin: "0 0 6px 0",
          textAlign: "center",
        }}
      >
        Calculate Your Savings
      </h3>
      <p
        style={{
          fontSize: "14px",
          color: "#B0B8C8",
          margin: "0 0 28px 0",
          textAlign: "center",
        }}
      >
        Select the departments you want to automate
      </p>

      {/* Department selection */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: "10px",
          marginBottom: "28px",
        }}
      >
        {Object.entries(DEPARTMENT_HOURS).map(([key, dept]) => {
          const isSelected = selected.includes(key);
          return (
            <button
              key={key}
              onClick={() => toggleDept(key)}
              style={{
                padding: "12px 14px",
                borderRadius: "10px",
                border: isSelected
                  ? "1px solid rgba(108, 99, 255, 0.5)"
                  : "1px solid rgba(255, 255, 255, 0.08)",
                background: isSelected
                  ? "rgba(108, 99, 255, 0.1)"
                  : "rgba(255, 255, 255, 0.02)",
                color: isSelected ? "#fff" : "#B0B8C8",
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
                textAlign: "left",
                fontFamily: "Inter, sans-serif",
                transition: "all 0.2s ease",
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: "2px" }}>
                {dept.name}
              </div>
              <div style={{ fontSize: "11px", opacity: 0.7 }}>
                ~{dept.hours}h/mo saved
              </div>
            </button>
          );
        })}
      </div>

      {/* Results */}
      {selected.length > 0 && (
        <div
          style={{
            background: "rgba(108, 99, 255, 0.05)",
            border: "1px solid rgba(108, 99, 255, 0.2)",
            borderRadius: "14px",
            padding: "24px",
          }}
        >
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(3, 1fr)",
              gap: "16px",
              marginBottom: "20px",
            }}
          >
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  fontSize: "28px",
                  fontWeight: 700,
                  color: "#00D4AA",
                }}
              >
                {totalHours}h
              </div>
              <div style={{ fontSize: "12px", color: "#B0B8C8" }}>
                Hours saved/mo
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  fontSize: "28px",
                  fontWeight: 700,
                  color: "#00D4AA",
                }}
              >
                {formatZAR(monthlySavings)}
              </div>
              <div style={{ fontSize: "12px", color: "#B0B8C8" }}>
                Monthly savings
              </div>
            </div>
            <div style={{ textAlign: "center" }}>
              <div
                style={{
                  fontSize: "28px",
                  fontWeight: 700,
                  color: "#6C63FF",
                }}
              >
                {roiMultiple}x
              </div>
              <div style={{ fontSize: "12px", color: "#B0B8C8" }}>
                Return on investment
              </div>
            </div>
          </div>

          <div
            style={{
              textAlign: "center",
              borderTop: "1px solid rgba(255, 255, 255, 0.06)",
              paddingTop: "16px",
            }}
          >
            <p
              style={{
                fontSize: "14px",
                color: "#B0B8C8",
                margin: "0 0 12px 0",
              }}
            >
              Recommended plan:{" "}
              <strong style={{ color: "#fff" }}>{suggestedPlan.name}</strong> at{" "}
              <strong style={{ color: "#00D4AA" }}>
                {formatZAR(suggestedPlan.price)}/mo
              </strong>{" "}
              vs{" "}
              <span style={{ textDecoration: "line-through", color: "#6B7280" }}>
                {formatZAR(totalSalary)}/mo
              </span>{" "}
              in staffing costs
            </p>
            {onSelectPlan && (
              <button
                onClick={() => onSelectPlan(suggestedPlan.slug)}
                style={{
                  background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
                  color: "#fff",
                  border: "none",
                  borderRadius: "10px",
                  padding: "12px 32px",
                  fontSize: "14px",
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "Inter, sans-serif",
                }}
              >
                Start Free Trial - {suggestedPlan.name} Plan
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
