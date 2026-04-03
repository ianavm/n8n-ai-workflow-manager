"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { FinanceKPIGrid } from "@/components/accounting/FinanceKPIGrid";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { ClientSelector } from "@/components/accounting/ClientSelector";
import { Clock, AlertTriangle, TrendingUp } from "lucide-react";

interface KPIData {
  total_receivables: number;
  total_payables: number;
  overdue_amount: number;
  overdue_invoices: number;
  cash_received_month: number;
  pending_approvals: number;
  reconciliation_pending: number;
  workflow_failures: number;
  invoices_sent_today: number;
  cash_received_today: number;
  bills_awaiting_approval: number;
  bills_due_this_week: number;
}

interface RecentInvoice {
  id: string;
  invoice_number: string;
  total: number;
  status: string;
  due_date: string;
  acct_customers: { legal_name: string } | null;
}

interface RecentTask {
  id: string;
  title: string;
  type: string;
  priority: string;
  status: string;
  created_at: string;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

export default function AccountingDashboard() {
  const supabase = createClient();
  const [kpis, setKpis] = useState<KPIData | null>(null);
  const [recentInvoices, setRecentInvoices] = useState<RecentInvoice[]>([]);
  const [openTasks, setOpenTasks] = useState<RecentTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeClientId, setActiveClientId] = useState<string>("");

  const loadData = useCallback(async (clientId: string) => {
    setLoading(true);
    const params = clientId ? `?client_id=${clientId}` : "";
    const [kpiRes, invRes, taskRes] = await Promise.all([
      fetch(`/api/accounting/dashboard${params}`).then((r) => r.json()),
      supabase
        .from("acct_invoices")
        .select("id, invoice_number, total, status, due_date, acct_customers(legal_name)")
        .eq("client_id", clientId)
        .order("created_at", { ascending: false })
        .limit(8),
      supabase
        .from("acct_tasks")
        .select("id, title, type, priority, status, created_at")
        .eq("client_id", clientId)
        .in("status", ["open", "in_progress"])
        .order("created_at", { ascending: false })
        .limit(5),
    ]);

    if (kpiRes.data) setKpis(kpiRes.data);
    if (invRes.data) setRecentInvoices(invRes.data as unknown as RecentInvoice[]);
    if (taskRes.data) setOpenTasks(taskRes.data as unknown as RecentTask[]);
    setLoading(false);
  }, [supabase]);

  const handleClientChange = useCallback((clientId: string) => {
    setActiveClientId(clientId);
    loadData(clientId);
  }, [loadData]);

  useEffect(() => {
    // Initial load — fetch config to get default client
    fetch("/api/accounting/config").then((r) => r.json()).then((result) => {
      const clientId = result.active_client_id;
      if (clientId) {
        setActiveClientId(clientId);
        loadData(clientId);
      } else {
        setLoading(false);
      }
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Finance Operations</h1>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  const emptyKpis: KPIData = {
    total_receivables: 0, total_payables: 0, overdue_amount: 0,
    overdue_invoices: 0, cash_received_month: 0, pending_approvals: 0,
    reconciliation_pending: 0, workflow_failures: 0, invoices_sent_today: 0,
    cash_received_today: 0, bills_awaiting_approval: 0, bills_due_this_week: 0,
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Finance Operations</h1>
        <div className="flex items-center gap-4">
          <ClientSelector onClientChange={handleClientChange} />
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <TrendingUp size={14} />
            <span>Live dashboard</span>
          </div>
        </div>
      </div>

      <FinanceKPIGrid data={kpis ?? emptyKpis} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Invoices */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] backdrop-blur-sm p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Recent Invoices</h2>
          {recentInvoices.length === 0 ? (
            <p className="text-sm text-gray-500">No invoices yet</p>
          ) : (
            <div className="space-y-3">
              {recentInvoices.map((inv) => (
                <a
                  key={inv.id}
                  href={`/admin/accounting/invoices/${inv.id}`}
                  className="flex items-center justify-between p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-white truncate">
                      {inv.invoice_number}
                    </p>
                    <p className="text-xs text-gray-400 truncate">
                      {inv.acct_customers?.legal_name ?? "Unknown"}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 ml-4">
                    <span className="text-sm font-medium text-white whitespace-nowrap">
                      {formatCurrency(inv.total)}
                    </span>
                    <InvoiceStatusBadge status={inv.status} />
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>

        {/* Open Tasks */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] backdrop-blur-sm p-5">
          <h2 className="text-sm font-semibold text-white mb-4">Open Tasks & Approvals</h2>
          {openTasks.length === 0 ? (
            <p className="text-sm text-gray-500">No pending tasks</p>
          ) : (
            <div className="space-y-3">
              {openTasks.map((task) => (
                <a
                  key={task.id}
                  href={`/admin/accounting/tasks`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                >
                  <div className={`rounded-full p-1.5 ${
                    task.priority === "urgent" ? "bg-red-500/20" :
                    task.priority === "high" ? "bg-orange-500/20" : "bg-yellow-500/20"
                  }`}>
                    {task.priority === "urgent" ? (
                      <AlertTriangle size={14} className="text-red-400" />
                    ) : (
                      <Clock size={14} className="text-yellow-400" />
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">{task.title}</p>
                    <p className="text-xs text-gray-400">
                      {task.type.replace(/_/g, " ")} &middot; {task.priority}
                    </p>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
