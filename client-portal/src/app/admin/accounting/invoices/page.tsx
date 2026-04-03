"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { FileText, Plus, Search, Filter } from "lucide-react";
import Link from "next/link";

interface Invoice {
  id: string;
  invoice_number: string;
  total: number;
  balance_due: number;
  status: string;
  issue_date: string;
  due_date: string;
  created_at: string;
  acct_customers: { legal_name: string } | null;
}

const STATUS_OPTIONS = [
  "all", "draft", "approved", "sent", "viewed",
  "payment_pending", "partially_paid", "paid", "overdue", "disputed", "cancelled",
];

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export default function InvoiceListPage() {
  const supabase = createClient();
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const limit = 20;

  const fetchInvoices = useCallback(async () => {
    setLoading(true);
    let query = supabase
      .from("acct_invoices")
      .select("id, invoice_number, total, balance_due, status, issue_date, due_date, created_at, acct_customers(legal_name)", { count: "exact" })
      .order("created_at", { ascending: false })
      .range((page - 1) * limit, page * limit - 1);

    if (statusFilter !== "all") {
      query = query.eq("status", statusFilter);
    }
    if (search) {
      query = query.or(`invoice_number.ilike.%${search}%,acct_customers.legal_name.ilike.%${search}%`);
    }

    const { data, count } = await query;
    setInvoices((data as unknown as Invoice[]) ?? []);
    setTotal(count ?? 0);
    setLoading(false);
  }, [supabase, statusFilter, search, page]);

  useEffect(() => {
    fetchInvoices();
  }, [fetchInvoices]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Invoice Tracker</h1>
        <Link
          href="/admin/accounting/invoices/new"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF6D5A] text-white text-sm font-medium hover:bg-[#e85d4a] transition-colors"
        >
          <Plus size={16} />
          Create Invoice
        </Link>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            type="text"
            placeholder="Search invoices..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="w-full pl-10 pr-4 py-2 rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.06)] text-white text-sm placeholder-gray-500 focus:outline-none focus:border-[rgba(255,109,90,0.3)]"
          />
        </div>
        <div className="relative">
          <Filter size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="pl-10 pr-8 py-2 rounded-lg bg-[rgba(0,0,0,0.2)] border border-[rgba(255,255,255,0.06)] text-white text-sm appearance-none focus:outline-none focus:border-[rgba(255,109,90,0.3)]"
          >
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s} className="bg-gray-900">
                {s === "all" ? "All Statuses" : s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Table */}
      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] backdrop-blur-sm overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Invoice</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Customer</th>
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
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : invoices.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                    <FileText className="mx-auto mb-2 text-gray-600" size={32} />
                    <p>No invoices found</p>
                  </td>
                </tr>
              ) : (
                invoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)] transition-colors">
                    <td className="px-4 py-3">
                      <Link href={`/admin/accounting/invoices/${inv.id}`} className="text-sm font-medium text-[#FF6D5A] hover:underline">
                        {inv.invoice_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-300">
                      {inv.acct_customers?.legal_name ?? "-"}
                    </td>
                    <td className="px-4 py-3 text-sm text-white text-right font-medium">
                      {formatCurrency(inv.total)}
                    </td>
                    <td className="px-4 py-3 text-sm text-right font-medium">
                      <span className={inv.balance_due > 0 ? "text-yellow-400" : "text-green-400"}>
                        {formatCurrency(inv.balance_due)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <InvoiceStatusBadge status={inv.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-400">
                      {formatDate(inv.due_date)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {total > limit && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[rgba(255,255,255,0.06)]">
            <p className="text-xs text-gray-400">
              Showing {(page - 1) * limit + 1}-{Math.min(page * limit, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => setPage(Math.max(1, page - 1))}
                disabled={page === 1}
                className="px-3 py-1 text-xs rounded bg-[rgba(255,255,255,0.05)] text-gray-300 disabled:opacity-30"
              >
                Previous
              </button>
              <button
                onClick={() => setPage(page + 1)}
                disabled={page * limit >= total}
                className="px-3 py-1 text-xs rounded bg-[rgba(255,255,255,0.05)] text-gray-300 disabled:opacity-30"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
