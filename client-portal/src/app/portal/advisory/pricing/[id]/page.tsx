"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, CheckCircle, Clock, Lock } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent } from "@/components/ui-shadcn/card";

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

function statusDisplay(status: string): {
  tone: "success" | "info" | "warning" | "danger" | "neutral";
  label: string;
} {
  const s = status.toLowerCase();
  if (s === "accepted" || s === "active") return { tone: "success", label: "Accepted" };
  if (s === "approved") return { tone: "info", label: "Approved" };
  if (s === "draft") return { tone: "warning", label: "Draft" };
  if (s === "expired") return { tone: "danger", label: "Expired" };
  return { tone: "neutral", label: status };
}

function formatCurrency(amount: number | null): string {
  if (amount == null) return "—";
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
  const [acceptMsg, setAcceptMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

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
      const res = await fetch(`/api/advisory/pricing/${pricingId}/accept`, { method: "POST" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setAcceptMsg({ type: "error", text: body.error || "Failed to accept agreement." });
      } else {
        setAcceptMsg({ type: "success", text: "Agreement accepted successfully." });
        setPricing({ ...pricing, status: "accepted", accepted_at: new Date().toISOString() });
        setTimeout(() => setAcceptMsg(null), 3000);
      }
    } catch {
      setAcceptMsg({ type: "error", text: "Failed to accept. Please try again." });
    }

    setAccepting(false);
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/portal/advisory/pricing" className="gap-1.5">
            <ArrowLeft className="size-3.5" />
            Back to fee agreements
          </Link>
        </Button>
        <LoadingState variant="card" rows={4} />
      </div>
    );
  }

  if (error || !pricing) {
    return (
      <div className="flex flex-col gap-6">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/portal/advisory/pricing" className="gap-1.5">
            <ArrowLeft className="size-3.5" />
            Back to fee agreements
          </Link>
        </Button>
        <ErrorState title="Fee agreement not found" description={error ?? "The agreement may have been removed."} />
      </div>
    );
  }

  const sc = statusDisplay(pricing.status);
  const canAccept = pricing.status.toLowerCase() === "approved";
  const isLocked =
    pricing.status.toLowerCase() === "accepted" || pricing.status.toLowerCase() === "active";

  return (
    <div className="flex flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link href="/portal/advisory/pricing" className="gap-1.5">
          <ArrowLeft className="size-3.5" />
          Back to fee agreements
        </Link>
      </Button>

      <PageHeader
        eyebrow="Advisory · Fee agreement"
        title={pricing.fee_type.replace(/_/g, " ")}
        actions={
          <div className="flex flex-col items-end gap-1">
            <Badge tone={sc.tone} appearance="soft">
              {sc.label}
            </Badge>
            {isLocked ? (
              <span className="inline-flex items-center gap-1 text-xs text-[var(--accent-teal)]">
                <Lock className="size-3" />
                Locked
              </span>
            ) : null}
            {pricing.accepted_at ? (
              <span className="inline-flex items-center gap-1 text-xs text-[var(--text-dim)]">
                <CheckCircle className="size-3" />
                Accepted {new Date(pricing.accepted_at).toLocaleDateString("en-ZA")}
              </span>
            ) : null}
          </div>
        }
      />

      <Card variant="default" accent="gradient-static" padding="lg">
        <CardContent className="flex flex-col gap-5">
          {pricing.amount != null || pricing.percentage != null ? (
            <div className="grid gap-5 md:grid-cols-2">
              {pricing.amount != null ? (
                <AmountBlock label="Amount" value={formatCurrency(pricing.amount)} color="var(--accent-teal)" />
              ) : null}
              {pricing.percentage != null ? (
                <AmountBlock label="Percentage" value={`${pricing.percentage}%`} color="var(--accent-purple)" />
              ) : null}
            </div>
          ) : null}

          {pricing.description ? (
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)] mb-1">
                Description
              </p>
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">{pricing.description}</p>
            </div>
          ) : null}

          <p className="flex items-center gap-1.5 text-xs text-[var(--text-dim)]">
            <Clock className="size-3" />
            Created {new Date(pricing.created_at).toLocaleDateString("en-ZA")}
            {pricing.version != null ? ` · Version ${pricing.version}` : ""}
          </p>

          {canAccept ? (
            <div className="pt-4 border-t border-[var(--border-subtle)] flex items-center gap-3">
              <Button variant="default" onClick={handleAccept} loading={accepting}>
                <CheckCircle className="size-4" />
                Accept agreement
              </Button>
              {acceptMsg ? (
                <span
                  className="text-sm font-medium"
                  style={{ color: acceptMsg.type === "success" ? "var(--accent-teal)" : "var(--danger)" }}
                >
                  {acceptMsg.text}
                </span>
              ) : null}
            </div>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}

function AmountBlock({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)] mb-1">
        {label}
      </p>
      <p className="text-2xl font-bold tabular-nums" style={{ color }}>
        {value}
      </p>
    </div>
  );
}
