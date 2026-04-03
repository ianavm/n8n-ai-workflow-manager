"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { BillStatusBadge } from "@/components/accounting/BillStatusBadge";
import { Package, Upload, Search } from "lucide-react";

interface Bill {
  id: string;
  bill_number: string | null;
  total_amount: number;
  status: string;
  due_date: string | null;
  extraction_confidence: number | null;
  created_at: string;
  acct_suppliers: { name: string } | null;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "-";
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export default function BillsPage() {
  const supabase = createClient();
  const [bills, setBills] = useState<Bill[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");

  const fetchBills = useCallback(async () => {
    setLoading(true);
    let query = supabase
      .from("acct_supplier_bills")
      .select("id, bill_number, total_amount, status, due_date, extraction_confidence, created_at, acct_suppliers(name)")
      .order("created_at", { ascending: false })
      .limit(50);

    if (statusFilter !== "all") query = query.eq("status", statusFilter);

    const { data } = await query;
    setBills((data as unknown as Bill[]) ?? []);
    setLoading(false);
  }, [supabase, statusFilter]);

  useEffect(() => { fetchBills(); }, [fetchBills]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Supplier Bills</h1>
        <button className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF6D5A] text-white text-sm font-medium hover:bg-[#e85d4a]">
          <Upload size={16} /> Upload Bill
        </button>
      </div>

      <div className="flex gap-2">
        {["all", "uploaded", "extracted", "awaiting_review", "approved", "paid", "rejected"].map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium transition-colors ${
              statusFilter === s
                ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] border border-[rgba(255,109,90,0.3)]"
                : "text-gray-400 hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
            }`}
          >
            {s === "all" ? "All" : s.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Supplier</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Bill #</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Amount</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Status</th>
              <th className="text-left px-4 py-3 text-xs font-medium text-gray-400 uppercase">Due Date</th>
              <th className="text-right px-4 py-3 text-xs font-medium text-gray-400 uppercase">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              Array.from({ length: 5 }).map((_, i) => (
                <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                  {Array.from({ length: 6 }).map((_, j) => (
                    <td key={j} className="px-4 py-3"><div className="h-4 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" /></td>
                  ))}
                </tr>
              ))
            ) : bills.length === 0 ? (
              <tr><td colSpan={6} className="px-4 py-12 text-center text-gray-500">
                <Package className="mx-auto mb-2 text-gray-600" size={32} />
                <p>No supplier bills</p>
              </td></tr>
            ) : (
              bills.map((bill) => (
                <tr key={bill.id} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)]">
                  <td className="px-4 py-3 text-sm text-white">{bill.acct_suppliers?.name ?? "Unknown"}</td>
                  <td className="px-4 py-3">
                    <a href={`/admin/accounting/bills/${bill.id}`} className="text-sm text-[#FF6D5A] hover:underline">
                      {bill.bill_number ?? "Pending"}
                    </a>
                  </td>
                  <td className="px-4 py-3 text-sm text-white text-right font-medium">{formatCurrency(bill.total_amount)}</td>
                  <td className="px-4 py-3"><BillStatusBadge status={bill.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-400">{formatDate(bill.due_date)}</td>
                  <td className="px-4 py-3 text-sm text-right">
                    {bill.extraction_confidence != null ? (
                      <span className={bill.extraction_confidence >= 70 ? "text-green-400" : "text-yellow-400"}>
                        {bill.extraction_confidence.toFixed(0)}%
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
