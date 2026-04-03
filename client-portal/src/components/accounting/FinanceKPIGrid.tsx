"use client";

import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  Clock,
  CheckCircle2,
} from "lucide-react";

interface KPIData {
  total_receivables: number;
  total_payables: number;
  overdue_amount: number;
  overdue_invoices: number;
  cash_received_month: number;
  pending_approvals: number;
  reconciliation_pending: number;
  workflow_failures: number;
}

interface FinanceKPIGridProps {
  data: KPIData;
  currency?: string;
}

function formatCurrency(cents: number, currency: string): string {
  const amount = cents / 100;
  if (currency === "ZAR") {
    return `R${amount.toLocaleString("en-ZA", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
  }
  return new Intl.NumberFormat("en-US", { style: "currency", currency }).format(amount);
}

function KPICard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] backdrop-blur-sm p-4">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2 ${color}`}>
          <Icon className="h-5 w-5 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs text-gray-400 truncate">{label}</p>
          <p className="text-lg font-semibold text-white truncate">{value}</p>
        </div>
      </div>
    </div>
  );
}

export function FinanceKPIGrid({ data, currency = "ZAR" }: FinanceKPIGridProps) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KPICard
        label="Total Receivables"
        value={formatCurrency(data.total_receivables, currency)}
        icon={TrendingUp}
        color="bg-blue-500/20"
      />
      <KPICard
        label="Total Payables"
        value={formatCurrency(data.total_payables, currency)}
        icon={TrendingDown}
        color="bg-purple-500/20"
      />
      <KPICard
        label="Overdue"
        value={`${data.overdue_invoices} (${formatCurrency(data.overdue_amount, currency)})`}
        icon={AlertTriangle}
        color="bg-red-500/20"
      />
      <KPICard
        label="Cash This Month"
        value={formatCurrency(data.cash_received_month, currency)}
        icon={DollarSign}
        color="bg-green-500/20"
      />
      <KPICard
        label="Pending Approvals"
        value={String(data.pending_approvals)}
        icon={Clock}
        color="bg-yellow-500/20"
      />
      <KPICard
        label="Reconciliation Pending"
        value={String(data.reconciliation_pending)}
        icon={CheckCircle2}
        color="bg-cyan-500/20"
      />
    </div>
  );
}
