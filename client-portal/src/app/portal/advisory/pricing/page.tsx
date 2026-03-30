"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  DollarSign,
  FileCheck,
  Clock,
  ChevronRight,
} from "lucide-react";

interface FaPricing {
  id: string;
  fee_type: string;
  amount: number | null;
  percentage: number | null;
  description: string | null;
  status: string;
  created_at: string;
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

export default function AdvisoryPricing() {
  const supabase = createClient();
  const [pricing, setPricing] = useState<FaPricing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchPricing = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: portalClient } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", userData.user.id)
      .single();

    if (!portalClient) {
      setError("No portal account found");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", portalClient.id)
      .single();

    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: pricingData, error: pricingErr } = await supabase
      .from("fa_pricing")
      .select("id, fee_type, amount, percentage, description, status, created_at")
      .eq("client_id", client.id)
      .order("created_at", { ascending: false });

    if (pricingErr) {
      setError(pricingErr.message);
      setLoading(false);
      return;
    }

    setPricing(pricingData || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchPricing();
  }, [fetchPricing]);

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

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Fee Agreements</h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          Your advisory fee structures and agreements.
        </p>
      </div>

      {pricing.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <DollarSign size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No fee agreements on record.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {pricing.map((p) => {
            const sc = statusConfig(p.status);

            return (
              <Link
                key={p.id}
                href={`/portal/advisory/pricing/${p.id}`}
                style={{ textDecoration: "none" }}
              >
                <div
                  style={{
                    ...glassCard,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "16px 20px",
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                    <div
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "12px",
                        background: "rgba(0,212,170,0.1)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      {sc.label === "Accepted" ? (
                        <FileCheck size={20} style={{ color: "#10B981" }} />
                      ) : (
                        <DollarSign size={20} style={{ color: "#00D4AA" }} />
                      )}
                    </div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                        {p.fee_type.replace(/_/g, " ")}
                      </div>
                      <div style={{ fontSize: "13px", color: "#6B7280", marginTop: "2px" }}>
                        {p.amount != null && formatCurrency(p.amount)}
                        {p.amount != null && p.percentage != null && " / "}
                        {p.percentage != null && `${p.percentage}%`}
                        {p.amount == null && p.percentage == null && "See details"}
                      </div>
                      <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "4px", display: "flex", alignItems: "center", gap: "4px" }}>
                        <Clock size={11} />
                        {new Date(p.created_at).toLocaleDateString("en-ZA")}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        background: sc.bg,
                        color: sc.color,
                      }}
                    >
                      {sc.label}
                    </span>
                    <ChevronRight size={16} style={{ color: "#6B7280" }} />
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
