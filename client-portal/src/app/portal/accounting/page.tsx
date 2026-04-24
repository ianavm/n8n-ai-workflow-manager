"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, Clock, DollarSign } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { KPIGrid } from "@/components/portal/KPIGrid";
import { StatCard } from "@/components/portal/StatCard";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";

interface Invoice {
  id: string;
  invoice_number: string;
  total: number;
  balance_due: number;
  status: string;
  due_date: string;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function ClientFinanceDashboard() {
  const supabase = createClient();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from("acct_invoices")
        .select("id, invoice_number, total, balance_due, status, due_date")
        .in("status", ["sent", "viewed", "payment_pending", "partially_paid", "overdue"])
        .order("due_date", { ascending: true })
        .limit(20);
      setInvoices((data as Invoice[]) ?? []);
      setLoading(false);
    }
    load();
  }, [supabase]);

  const totalOutstanding = invoices.reduce((sum, inv) => sum + inv.balance_due, 0);
  const overdueCount = invoices.filter((inv) => inv.status === "overdue").length;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Finance"
        title="Accounting overview"
        description="Outstanding invoices, overdue balances, and recent transactions."
      />

      <KPIGrid cols={2}>
        <StatCard
          label="Outstanding balance"
          value={totalOutstanding / 100}
          prefix="R"
          decimals={2}
          icon={<DollarSign className="size-4" aria-hidden />}
          accent="warning"
          cardAccent="coral"
          loading={loading}
          gradientNumber
        />
        <StatCard
          label="Overdue invoices"
          value={overdueCount}
          icon={<Clock className="size-4" aria-hidden />}
          accent="danger"
          loading={loading}
        />
      </KPIGrid>

      <Card variant="default" padding="lg">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base">Outstanding invoices</CardTitle>
            <Button asChild variant="ghost" size="sm">
              <Link href="/portal/accounting/invoices">
                View all
                <ArrowUpRight className="size-3.5" />
              </Link>
            </Button>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {loading ? (
            <LoadingState variant="list" rows={3} />
          ) : invoices.length === 0 ? (
            <EmptyState inline title="No outstanding invoices" description="You're all caught up." />
          ) : (
            <ul className="flex flex-col divide-y divide-[var(--border-subtle)]">
              {invoices.map((inv) => (
                <li key={inv.id}>
                  <Link
                    href={`/portal/accounting/invoices/${inv.id}`}
                    className="flex items-center justify-between gap-3 py-3 group"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground group-hover:text-[var(--brand-primary)] transition-colors truncate">
                        {inv.invoice_number}
                      </p>
                      <p className="text-xs text-[var(--text-dim)]">Due {formatDate(inv.due_date)}</p>
                    </div>
                    <div className="flex items-center gap-3 shrink-0">
                      <span className="text-sm font-semibold text-foreground tabular-nums">
                        {formatCurrency(inv.balance_due)}
                      </span>
                      <InvoiceStatusBadge status={inv.status} />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
