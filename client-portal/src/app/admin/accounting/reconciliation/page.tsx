"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { PaymentStatusBadge } from "@/components/accounting/PaymentStatusBadge";
import { ArrowLeftRight, CheckCircle2 } from "lucide-react";

interface Payment {
  id: string;
  amount: number;
  date_received: string;
  method: string;
  reference_text: string | null;
  reconciliation_status: string;
  match_confidence: number | null;
  invoice_id: string | null;
  acct_invoices: { invoice_number: string; total: number } | null;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    month: "short", day: "numeric",
  });
}

export default function ReconciliationPage() {
  const supabase = createClient();
  const [payments, setPayments] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"unmatched" | "all">("unmatched");

  useEffect(() => {
    async function load() {
      let query = supabase
        .from("acct_payments")
        .select("id, amount, date_received, method, reference_text, reconciliation_status, match_confidence, invoice_id, acct_invoices(invoice_number, total)")
        .order("date_received", { ascending: false })
        .limit(50);

      if (filter === "unmatched") {
        query = query.in("reconciliation_status", ["received", "matching", "unmatched", "partial"]);
      }

      const { data } = await query;
      setPayments((data as unknown as Payment[]) ?? []);
      setLoading(false);
    }
    load();
  }, [supabase, filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Reconciliation Centre</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setFilter("unmatched")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium ${
              filter === "unmatched" ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A]" : "text-gray-400"
            }`}
          >
            Needs Attention
          </button>
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium ${
              filter === "all" ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A]" : "text-gray-400"
            }`}
          >
            All
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Date</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Amount</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Method</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Reference</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Matched To</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                  {Array.from({ length: 7 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-4 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" /></td>
                  ))}
                </tr>
              ))
            ) : payments.length === 0 ? (
              <tr><td colSpan={7} className="px-4 py-12 text-center text-gray-500">
                <CheckCircle2 className="mx-auto mb-2 text-green-500" size={32} />
                <p>All payments reconciled</p>
              </td></tr>
            ) : (
              payments.map((p) => (
                <tr key={p.id} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)]">
                  <td className="px-4 py-3 text-sm text-gray-300">{formatDate(p.date_received)}</td>
                  <td className="px-4 py-3 text-sm text-white text-right font-medium">{formatCurrency(p.amount)}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 uppercase">{p.method}</td>
                  <td className="px-4 py-3 text-xs text-gray-400 truncate max-w-[150px]">{p.reference_text ?? "-"}</td>
                  <td className="px-4 py-3 text-xs">
                    {p.acct_invoices ? (
                      <span className="text-[#FF6D5A]">{p.acct_invoices.invoice_number}</span>
                    ) : (
                      <span className="text-gray-500">Unmatched</span>
                    )}
                  </td>
                  <td className="px-4 py-3"><PaymentStatusBadge status={p.reconciliation_status} /></td>
                  <td className="px-4 py-3 text-xs text-right">
                    {p.match_confidence != null ? (
                      <span className={p.match_confidence >= 80 ? "text-green-400" : p.match_confidence >= 50 ? "text-yellow-400" : "text-red-400"}>
                        {p.match_confidence.toFixed(0)}%
                      </span>
                    ) : "-"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
