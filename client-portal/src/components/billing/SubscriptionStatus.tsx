"use client";

import { format } from "date-fns";

interface SubscriptionStatusProps {
  planName: string;
  planSlug: string;
  status: "active" | "trialing" | "past_due" | "canceled" | "incomplete" | "unpaid" | "paused";
  billingInterval: "monthly" | "yearly";
  periodEnd: string;
  trialEnd: string | null;
  cancelAtPeriodEnd: boolean;
  priceMonthly: number;
  priceYearly: number;
  onChangePlan: () => void;
  onCancel: () => void;
  onReactivate: () => void;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

const statusConfig: Record<
  string,
  { color: string; label: string }
> = {
  active: { color: "#00D4AA", label: "Active" },
  trialing: { color: "#F59E0B", label: "Trial" },
  past_due: { color: "#FF6D5A", label: "Past Due" },
  canceled: { color: "#FF6D5A", label: "Canceled" },
  incomplete: { color: "#6B7280", label: "Incomplete" },
};

export function SubscriptionStatus({
  planName,
  status,
  billingInterval,
  periodEnd,
  trialEnd,
  cancelAtPeriodEnd,
  priceMonthly,
  priceYearly,
  onChangePlan,
  onCancel,
  onReactivate,
}: SubscriptionStatusProps) {
  const statusInfo = statusConfig[status] || statusConfig.incomplete;
  const price = billingInterval === "monthly" ? priceMonthly : priceYearly;

  return (
    <div
      style={{
        background: "rgba(255, 255, 255, 0.05)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "16px",
        padding: "28px",
        fontFamily: "Inter, sans-serif",
      }}
    >
      {/* Top row: Plan badge + Status */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          marginBottom: "20px",
          flexWrap: "wrap",
          gap: "12px",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {/* Plan name badge */}
          <span
            style={{
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              color: "#fff",
              fontSize: "13px",
              fontWeight: 700,
              padding: "6px 16px",
              borderRadius: "20px",
            }}
          >
            {planName}
          </span>

          {/* Status dot + label */}
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              fontSize: "13px",
              color: statusInfo.color,
              fontWeight: 600,
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: statusInfo.color,
                display: "inline-block",
              }}
            />
            {statusInfo.label}
          </span>
        </div>

        {/* Price */}
        <span style={{ fontSize: "14px", color: "#B0B8C8" }}>
          {formatZAR(price)}/{billingInterval === "monthly" ? "mo" : "yr"}
        </span>
      </div>

      {/* Middle: Billing / trial info */}
      <div style={{ marginBottom: "20px" }}>
        {status === "trialing" && trialEnd ? (
          <p style={{ fontSize: "14px", color: "#B0B8C8", margin: 0 }}>
            Trial ends:{" "}
            <span style={{ color: "#fff", fontWeight: 500 }}>
              {format(new Date(trialEnd), "MMMM d, yyyy")}
            </span>
          </p>
        ) : (
          <p style={{ fontSize: "14px", color: "#B0B8C8", margin: 0 }}>
            Next billing:{" "}
            <span style={{ color: "#fff", fontWeight: 500 }}>
              {format(new Date(periodEnd), "MMMM d, yyyy")}
            </span>
          </p>
        )}
      </div>

      {/* Cancel warning */}
      {cancelAtPeriodEnd && (
        <div
          style={{
            background: "rgba(255, 109, 90, 0.08)",
            border: "1px solid rgba(255, 109, 90, 0.2)",
            borderRadius: "10px",
            padding: "12px 16px",
            marginBottom: "20px",
          }}
        >
          <p
            style={{
              fontSize: "13px",
              color: "#FF6D5A",
              margin: 0,
              fontWeight: 500,
            }}
          >
            Your subscription cancels on{" "}
            {format(new Date(periodEnd), "MMMM d, yyyy")}. You will retain
            access until then.
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "12px", flexWrap: "wrap" }}>
        {cancelAtPeriodEnd ? (
          <button
            className="btn-gradient"
            onClick={onReactivate}
            style={{
              padding: "10px 20px",
              borderRadius: "12px",
              fontSize: "14px",
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "Inter, sans-serif",
            }}
          >
            Reactivate
          </button>
        ) : (
          <>
            <button
              className="btn-outline"
              onClick={onChangePlan}
              style={{
                padding: "10px 20px",
                borderRadius: "12px",
                fontSize: "14px",
                fontWeight: 600,
                cursor: "pointer",
                fontFamily: "Inter, sans-serif",
              }}
            >
              Change Plan
            </button>
            {status !== "canceled" && (
              <button
                className="btn-outline"
                onClick={onCancel}
                style={{
                  padding: "10px 20px",
                  borderRadius: "12px",
                  fontSize: "14px",
                  fontWeight: 600,
                  cursor: "pointer",
                  fontFamily: "Inter, sans-serif",
                  color: "#B0B8C8",
                  transition: "color 0.2s ease, border-color 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = "#FF6D5A";
                  e.currentTarget.style.borderColor = "#FF6D5A";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = "#B0B8C8";
                  e.currentTarget.style.borderColor = "";
                }}
              >
                Cancel Subscription
              </button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
