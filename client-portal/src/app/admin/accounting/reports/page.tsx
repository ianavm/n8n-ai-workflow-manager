"use client";

import { useEffect, useState } from "react";
import { BarChart3, TrendingUp, TrendingDown } from "lucide-react";

interface AgedData {
  current: number;
  days_30: number;
  days_60: number;
  days_90: number;
  days_120_plus: number;
  total: number;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

function AgedBar({ label, amount, total, color }: { label: string; amount: number; total: number; color: string }) {
  const pct = total > 0 ? (amount / total) * 100 : 0;
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-gray-400">{label}</span>
        <span className="text-white font-medium">{formatCurrency(amount)}</span>
      </div>
      <div className="h-2 rounded-full bg-[rgba(255,255,255,0.05)] overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

export default function ReportsPage() {
  const [receivables, setReceivables] = useState<AgedData | null>(null);
  const [payables, setPayables] = useState<AgedData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [recRes, payRes] = await Promise.all([
        fetch("/api/accounting/reports/aged-receivables").then((r) => r.json()),
        fetch("/api/accounting/reports/aged-payables").then((r) => r.json()),
      ]);
      if (recRes.data) setReceivables(recRes.data);
      if (payRes.data) setPayables(payRes.data);
      setLoading(false);
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Reports & Insights</h1>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {Array.from({ length: 2 }).map((_, i) => (
            <div key={i} className="h-64 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Reports & Insights</h1>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Aged Receivables */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <div className="flex items-center gap-2">
            <TrendingUp size={18} className="text-blue-400" />
            <h2 className="text-sm font-semibold text-white">Aged Receivables</h2>
            {receivables && (
              <span className="ml-auto text-sm font-bold text-white">{formatCurrency(receivables.total)}</span>
            )}
          </div>
          {receivables ? (
            <div className="space-y-3">
              <AgedBar label="Current" amount={receivables.current} total={receivables.total} color="bg-green-500" />
              <AgedBar label="30 Days" amount={receivables.days_30} total={receivables.total} color="bg-yellow-500" />
              <AgedBar label="60 Days" amount={receivables.days_60} total={receivables.total} color="bg-orange-500" />
              <AgedBar label="90 Days" amount={receivables.days_90} total={receivables.total} color="bg-red-500" />
              <AgedBar label="120+ Days" amount={receivables.days_120_plus} total={receivables.total} color="bg-red-700" />
            </div>
          ) : (
            <p className="text-sm text-gray-500">No data available</p>
          )}
        </div>

        {/* Aged Payables */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <div className="flex items-center gap-2">
            <TrendingDown size={18} className="text-purple-400" />
            <h2 className="text-sm font-semibold text-white">Aged Payables</h2>
            {payables && (
              <span className="ml-auto text-sm font-bold text-white">{formatCurrency(payables.total)}</span>
            )}
          </div>
          {payables ? (
            <div className="space-y-3">
              <AgedBar label="Current" amount={payables.current} total={payables.total} color="bg-green-500" />
              <AgedBar label="30 Days" amount={payables.days_30} total={payables.total} color="bg-yellow-500" />
              <AgedBar label="60 Days" amount={payables.days_60} total={payables.total} color="bg-orange-500" />
              <AgedBar label="90 Days" amount={payables.days_90} total={payables.total} color="bg-red-500" />
              <AgedBar label="120+ Days" amount={payables.days_120_plus} total={payables.total} color="bg-red-700" />
            </div>
          ) : (
            <p className="text-sm text-gray-500">No data available</p>
          )}
        </div>
      </div>
    </div>
  );
}
