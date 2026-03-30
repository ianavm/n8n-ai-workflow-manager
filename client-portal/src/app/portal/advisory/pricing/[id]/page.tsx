"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  ArrowLeft,
  DollarSign,
  Lock,
  CheckCircle,
  Clock,
} from "lucide-react";

interface PricingDetail {
  id: string;
  fee_type: string;
  amount: number | null;
  percentage: number | null;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string | null;
  version: number | null;
  accepted_at: string | null;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

function statusConfig(status: string) {
  const s = status.toLowerCase();
  if (s === "accepted" || s === "active")
    return { color: "#10B981", bg: "rgba(16,185,129,0.1)", label: "Accepted" };
  if (s === "approved")
    return { color: "#00A651", bg: "rgba(108,99,255,0.1)", label: "Approved" };
  if (s === "draft")
    return { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", label: "Draft" };
  if (s === "expired")
    return { color: "#EF4444", bg: "rgba(239,68,68,0.1)", label: "Expired" };
  return { color: "#6B7280", bg: "rgba(107,114,128,0.1)", label: status };
}

function formatCurrency(amount: number | null): string {
  if (amount == null) return "---";
  return `R${amount.toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

export default function PricingDetailPage() {
  const params = useParams();
  const pricingId = params.id as string;
  const supabase = createClient();
  const [pricing, setPricing] = useState<PricingDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);
  const [acceptMsg, setAcceptMsg] = useState<string | null>(null);

  const fetchPricing = useCallback(async () => {
    setLoading(true);

    const { data: pricingData, error: pricingErr } = await supabase
      .from("fa_pricing")
      .select("*")
      .eq("id", pricingId)
      .single();

    if (pricingErr || !pricingData) {
      setError("Fee agreement not found.");
      setLoading(false);
      return;
    }

    setPricing(pricingData);
    setLoading(false);
  }, [supabase, pricingId]);

  useEffect(() => {
    fetchPricing();
  }, [fetchPricing]);

  async function handleAccept() {
    if (!pricing) return;
    setAccepting(true);
    setAcceptMsg(null);

    try {
      const res = await fetch(`/api/advisory/pricing/${pricingId}/accept`, {
        method: "POST",
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setAcceptMsg(body.error || "Failed to accept agreement.");
      } else {
        setAcceptMsg("Agreement accepted successfully.");
        setPricing({ ...pricing, status: "accepted", accepted_at: new Date().toISOString() });
        setTimeout(() => setAcceptMsg(null), 3000);
      }
    } catch {
      setAcceptMsg("Failed to accept. Please try again.");
    }

    setAccepting(false);
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #00A651",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  if (error || !pricing) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error || "Not found."}</p>
        <Link href="/portal/advisory/pricing" style={{ color: "#00A651", fontSize: "13px", marginTop: "8px", display: "inline-block" }}>
          Back to Fee Agreements
        </Link>
      </div>
    );
  }

  const sc = statusConfig(pricing.status);
  const canAccept = pricing.status.toLowerCase() === "approved";
  const isLocked = pricing.status.toLowerCase() === "accepted" || pricing.status.toLowerCase() === "active";

  return (
    <div>
      {/* Back link */}
      <Link
        href="/portal/advisory/pricing"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          color: "#6B7280",
          fontSize: "13px",
          textDecoration: "none",
          marginBottom: "20px",
        }}
      >
        <ArrowLeft size={14} />
        Back to Fee Agreements
      </Link>

      {/* Header card */}
      <div style={{ ...glassCard, marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <h1 style={{ fontSize: "22px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>
              {pricing.fee_type.replace(/_/g, " ")}
            </h1>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "16px" }}>
              {pricing.amount != null && (
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Amount
                  </label>
                  <div style={{ fontSize: "20px", fontWeight: 700, color: "#00D4AA", marginTop: "4px" }}>
                    {formatCurrency(pricing.amount)}
                  </div>
                </div>
              )}
              {pricing.percentage != null && (
                <div>
                  <label style={{ fontSize: "12px", fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                    Percentage
                  </label>
                  <div style={{ fontSize: "20px", fontWeight: 700, color: "#00A651", marginTop: "4px" }}>
                    {pricing.percentage}%
                  </div>
                </div>
              )}
            </div>

            {pricing.description && (
              <div style={{ marginTop: "16px" }}>
                <label style={{ fontSize: "12px", fontWeight: 600, color: "#6B7280", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                  Description
                </label>
                <p style={{ fontSize: "14px", color: "#B0B8C8", marginTop: "6px", lineHeight: "1.6" }}>
                  {pricing.description}
                </p>
              </div>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "8px" }}>
            <span
              style={{
                padding: "4px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                background: sc.bg,
                color: sc.color,
              }}
            >
              {sc.label}
            </span>

            {isLocked && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#10B981" }}>
                <Lock size={12} />
                Locked
              </div>
            )}

            {pricing.accepted_at && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: "#6B7280" }}>
                <CheckCircle size={12} />
                Accepted {new Date(pricing.accepted_at).toLocaleDateString("en-ZA")}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "8px", marginTop: "20px", fontSize: "12px", color: "#6B7280" }}>
          <Clock size={12} />
          Created {new Date(pricing.created_at).toLocaleDateString("en-ZA")}
          {pricing.version != null && ` - Version ${pricing.version}`}
        </div>

        {/* Accept button */}
        {canAccept && (
          <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
              <button
                onClick={handleAccept}
                disabled={accepting}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 20px",
                  borderRadius: "10px",
                  background: "linear-gradient(135deg, #10B981, #059669)",
                  color: "#fff",
                  fontSize: "14px",
                  fontWeight: 600,
                  border: "none",
                  cursor: accepting ? "not-allowed" : "pointer",
                  opacity: accepting ? 0.6 : 1,
                  fontFamily: "inherit",
                }}
              >
                <CheckCircle size={16} />
                {accepting ? "Accepting..." : "Accept Agreement"}
              </button>
              {acceptMsg && (
                <span style={{ fontSize: "13px", color: acceptMsg.includes("Failed") ? "#EF4444" : "#10B981" }}>
                  {acceptMsg}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Version info shown inline above */}
    </div>
  );
}
