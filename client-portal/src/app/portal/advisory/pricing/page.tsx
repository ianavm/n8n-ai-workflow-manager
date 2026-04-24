"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ChevronRight, Clock, DollarSign, FileCheck } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";

interface FaPricing {
  id: string;
  fee_type: string;
  amount: number | null;
  percentage: number | null;
  description: string | null;
  status: string;
  created_at: string;
}

function statusConfig(status: string): {
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
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Fee agreements" description="Your advisory fee structures and agreements." />
        <LoadingState variant="list" rows={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Fee agreements" description="Your advisory fee structures and agreements." />
        <ErrorState title="Unable to load fee agreements" description={error} onRetry={fetchPricing} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Advisory"
        title="Fee agreements"
        description="Your advisory fee structures and agreements."
      />

      {pricing.length === 0 ? (
        <EmptyState icon={<DollarSign className="size-5" />} title="No fee agreements on record" />
      ) : (
        <ul className="flex flex-col gap-3">
          {pricing.map((p) => {
            const sc = statusConfig(p.status);
            const isAccepted = sc.label === "Accepted";
            return (
              <li key={p.id}>
                <Link href={`/portal/advisory/pricing/${p.id}`}>
                  <Card variant="interactive" padding="md">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="grid place-items-center size-10 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-teal)_12%,transparent)] text-[var(--accent-teal)] shrink-0">
                          {isAccepted ? <FileCheck className="size-4" /> : <DollarSign className="size-4" />}
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground capitalize">
                            {p.fee_type.replace(/_/g, " ")}
                          </p>
                          <p className="text-sm text-[var(--text-muted)] mt-0.5">
                            {p.amount != null ? formatCurrency(p.amount) : null}
                            {p.amount != null && p.percentage != null ? " / " : null}
                            {p.percentage != null ? `${p.percentage}%` : null}
                            {p.amount == null && p.percentage == null ? "See details" : null}
                          </p>
                          <p className="flex items-center gap-1 text-xs text-[var(--text-dim)] mt-1">
                            <Clock className="size-3" />
                            {new Date(p.created_at).toLocaleDateString("en-ZA")}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        <Badge tone={sc.tone} appearance="soft" size="sm">
                          {sc.label}
                        </Badge>
                        <ChevronRight className="size-4 text-[var(--text-dim)]" aria-hidden />
                      </div>
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
