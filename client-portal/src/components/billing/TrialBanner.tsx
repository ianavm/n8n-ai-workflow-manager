"use client";

import { useState } from "react";
import { Clock, X } from "lucide-react";
import { format, differenceInDays } from "date-fns";

interface TrialBannerProps {
  trialEnd: string;
  planName: string;
  amount: number;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

export function TrialBanner({ trialEnd, planName, amount }: TrialBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  const trialDate = new Date(trialEnd);
  const daysLeft = differenceInDays(trialDate, new Date());
  const isUrgent = daysLeft <= 3;

  const bgColor = isUrgent
    ? "rgba(255, 109, 90, 0.08)"
    : "rgba(108, 99, 255, 0.08)";
  const borderGradient = isUrgent
    ? "linear-gradient(to bottom, #FF6D5A, #FF6D5A)"
    : "linear-gradient(to bottom, #6C63FF, #00D4AA)";
  const iconColor = isUrgent ? "#F59E0B" : "#6C63FF";

  return (
    <div
      style={{
        position: "relative",
        background: bgColor,
        borderRadius: "12px",
        padding: "16px 48px 16px 20px",
        display: "flex",
        alignItems: "center",
        gap: "14px",
        fontFamily: "Inter, sans-serif",
        borderLeft: "3px solid transparent",
        borderImage: borderGradient,
        borderImageSlice: 1,
      }}
    >
      {/* Icon */}
      <Clock
        size={20}
        style={{ color: iconColor, flexShrink: 0 }}
      />

      {/* Text */}
      <p style={{ margin: 0, fontSize: "14px", color: "#B0B8C8", lineHeight: 1.5 }}>
        Your 14-day free trial ends on{" "}
        <span style={{ color: "#fff", fontWeight: 600 }}>
          {format(trialDate, "MMMM d, yyyy")}
        </span>
        . Your card will be charged{" "}
        <span style={{ color: "#fff", fontWeight: 600 }}>
          {formatZAR(amount)}
        </span>{" "}
        for the{" "}
        <span style={{ color: "#fff", fontWeight: 600 }}>{planName}</span> plan.
      </p>

      {/* Dismiss button */}
      <button
        onClick={() => setDismissed(true)}
        style={{
          position: "absolute",
          top: "50%",
          right: "14px",
          transform: "translateY(-50%)",
          background: "transparent",
          border: "none",
          color: "#6B7280",
          cursor: "pointer",
          padding: "4px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "color 0.2s ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.color = "#fff";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.color = "#6B7280";
        }}
      >
        <X size={16} />
      </button>
    </div>
  );
}
