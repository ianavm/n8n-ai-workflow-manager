"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { DollarSign, FileText, Clock, CreditCard } from "lucide-react";
import Link from "next/link";

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
    year: "numeric", month: "short", day: "numeric",
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
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Finance</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg p-2 bg-yellow-500/20">
              <DollarSign className="h-5 w-5 text-yellow-400" />
            </div>
            <div>
              <p className="text-xs text-gray-400">Outstanding Balance</p>
              <p className="text-lg font-semibold text-white">{formatCurrency(totalOutstanding)}</p>
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-4">
          <div className="flex items-center gap-3">
            <div className="rounded-lg p-2 bg-red-500/20">
              <Clock className="h-5 w-5 text-red-400" />
            </div>
            <div>
              <p className="text-xs text-gray-400">Overdue Invoices</p>
              <p className="text-lg font-semibold text-white">{overdueCount}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Outstanding Invoices */}
      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-white">Outstanding Invoices</h2>
          <Link href="/portal/accounting/invoices" className="text-xs text-[#FF6D5A] hover:underline">
            View all
          </Link>
        </div>
        {loading ? (
          <div className="space-y-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 rounded-lg bg-[rgba(255,255,255,0.03)] animate-pulse" />
            ))}
          </div>
        ) : invoices.length === 0 ? (
          <p className="text-sm text-gray-500 text-center py-8">No outstanding invoices</p>
        ) : (
          <div className="space-y-2">
            {invoices.map((inv) => (
              <Link
                key={inv.id}
                href={`/portal/accounting/invoices/${inv.id}`}
                className="flex items-center justify-between p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
              >
                <div>
                  <p className="text-sm font-medium text-white">{inv.invoice_number}</p>
                  <p className="text-xs text-gray-400">Due: {formatDate(inv.due_date)}</p>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm font-medium text-white">{formatCurrency(inv.balance_due)}</span>
                  <InvoiceStatusBadge status={inv.status} />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
