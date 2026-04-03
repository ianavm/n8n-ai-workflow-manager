"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { FileText } from "lucide-react";
import Link from "next/link";

interface Invoice {
  id: string;
  invoice_number: string;
  total: number;
  balance_due: number;
  status: string;
  issue_date: string;
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

export default function ClientInvoiceListPage() {
  const supabase = createClient();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from("acct_invoices")
        .select("id, invoice_number, total, balance_due, status, issue_date, due_date")
        .neq("status", "draft")
        .order("created_at", { ascending: false })
        .limit(50);
      setInvoices((data as Invoice[]) ?? []);
      setLoading(false);
    }
    load();
  }, [supabase]);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">My Invoices</h1>

      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Invoice</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Total</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Balance</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Due Date</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                  {Array.from({ length: 5 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-4 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" /></td>
                  ))}
                </tr>
              ))
            ) : invoices.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-12 text-center text-gray-500">
                <FileText className="mx-auto mb-2 text-gray-600" size={32} />
                <p>No invoices</p>
              </td></tr>
            ) : (
              invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)]">
                  <td className="px-4 py-3">
                    <Link href={`/portal/accounting/invoices/${inv.id}`} className="text-sm font-medium text-[#FF6D5A] hover:underline">
                      {inv.invoice_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-sm text-white text-right font-medium">{formatCurrency(inv.total)}</td>
                  <td className="px-4 py-3 text-sm text-right font-medium">
                    <span className={inv.balance_due > 0 ? "text-yellow-400" : "text-green-400"}>
                      {formatCurrency(inv.balance_due)}
                    </span>
                  </td>
                  <td className="px-4 py-3"><InvoiceStatusBadge status={inv.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-400">{formatDate(inv.due_date)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
