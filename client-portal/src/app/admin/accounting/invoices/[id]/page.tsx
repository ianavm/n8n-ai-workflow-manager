"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import {
  Send,
  CheckCircle2,
  XCircle,
  FileText,
  ArrowLeft,
  Clock,
} from "lucide-react";
import Link from "next/link";

interface LineItem {
  item_code: string;
  description: string;
  qty: number;
  unit_price: number;
  vat_rate: number;
  line_total: number;
}

interface Invoice {
  id: string;
  invoice_number: string;
  reference: string | null;
  issue_date: string;
  due_date: string;
  status: string;
  subtotal: number;
  vat_amount: number;
  total: number;
  amount_paid: number;
  balance_due: number;
  currency: string;
  line_items: LineItem[];
  pdf_url: string | null;
  payment_link: string | null;
  source: string;
  reminder_count: number;
  dispute_reason: string | null;
  notes: string | null;
  created_by: string | null;
  sent_at: string | null;
  paid_at: string | null;
  created_at: string;
  acct_customers: {
    legal_name: string;
    email: string | null;
    phone: string | null;
    billing_address: string | null;
  } | null;
}

interface AuditEntry {
  id: number;
  event_type: string;
  action: string;
  actor: string;
  result: string;
  created_at: string;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    year: "numeric", month: "short", day: "numeric",
  });
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-ZA", {
    year: "numeric", month: "short", day: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}

export default function InvoiceDetailPage() {
  const params = useParams();
  const invoiceId = params.id as string;
  const supabase = createClient();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [auditLog, setAuditLog] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const [invRes, auditRes] = await Promise.all([
        supabase
          .from("acct_invoices")
          .select("*, acct_customers(legal_name, email, phone, billing_address)")
          .eq("id", invoiceId)
          .single(),
        supabase
          .from("acct_audit_log")
          .select("id, event_type, action, actor, result, created_at")
          .eq("entity_type", "invoice")
          .eq("entity_id", invoiceId)
          .order("created_at", { ascending: false })
          .limit(20),
      ]);

      if (invRes.data) setInvoice(invRes.data as Invoice);
      if (auditRes.data) setAuditLog(auditRes.data);
      setLoading(false);
    }
    load();
  }, [supabase, invoiceId]);

  async function handleAction(action: "approve" | "send" | "cancel") {
    if (!invoice) return;
    setActionLoading(action);

    const endpoint = `/api/accounting/invoices/${invoice.id}/${action}`;
    const resp = await fetch(endpoint, { method: "POST" });
    const result = await resp.json();

    if (resp.ok && result.data) {
      setInvoice({ ...invoice, ...result.data });
    }
    setActionLoading(null);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 bg-[rgba(255,255,255,0.05)] rounded animate-pulse" />
        <div className="h-64 bg-[rgba(0,0,0,0.2)] rounded-xl animate-pulse" />
      </div>
    );
  }

  if (!invoice) {
    return (
      <div className="text-center py-12">
        <FileText className="mx-auto mb-4 text-gray-600" size={48} />
        <p className="text-gray-400">Invoice not found</p>
        <Link href="/admin/accounting/invoices" className="text-[#FF6D5A] text-sm mt-2 inline-block">
          Back to invoices
        </Link>
      </div>
    );
  }

  const canApprove = invoice.status === "draft";
  const canSend = invoice.status === "approved";
  const canCancel = !["paid", "cancelled"].includes(invoice.status);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/admin/accounting/invoices" className="text-gray-400 hover:text-white transition-colors">
            <ArrowLeft size={20} />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-white">{invoice.invoice_number}</h1>
            <p className="text-sm text-gray-400">{invoice.acct_customers?.legal_name ?? "Unknown Customer"}</p>
          </div>
          <InvoiceStatusBadge status={invoice.status} />
        </div>
        <div className="flex items-center gap-2">
          {canApprove && (
            <button
              onClick={() => handleAction("approve")}
              disabled={actionLoading === "approve"}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-green-600 text-white text-sm font-medium hover:bg-green-700 disabled:opacity-50"
            >
              <CheckCircle2 size={16} />
              {actionLoading === "approve" ? "Approving..." : "Approve"}
            </button>
          )}
          {canSend && (
            <button
              onClick={() => handleAction("send")}
              disabled={actionLoading === "send"}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF6D5A] text-white text-sm font-medium hover:bg-[#e85d4a] disabled:opacity-50"
            >
              <Send size={16} />
              {actionLoading === "send" ? "Sending..." : "Send Invoice"}
            </button>
          )}
          {canCancel && (
            <button
              onClick={() => handleAction("cancel")}
              disabled={actionLoading === "cancel"}
              className="flex items-center gap-2 px-3 py-2 rounded-lg border border-red-500/30 text-red-400 text-sm hover:bg-red-500/10 disabled:opacity-50"
            >
              <XCircle size={16} />
              Cancel
            </button>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Invoice Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Summary */}
          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div>
                <p className="text-xs text-gray-400">Issue Date</p>
                <p className="text-sm text-white">{formatDate(invoice.issue_date)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Due Date</p>
                <p className="text-sm text-white">{formatDate(invoice.due_date)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Reference</p>
                <p className="text-sm text-white">{invoice.reference ?? "-"}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Source</p>
                <p className="text-sm text-white capitalize">{invoice.source}</p>
              </div>
            </div>
          </div>

          {/* Line Items */}
          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
            <div className="px-5 py-3 border-b border-[rgba(255,255,255,0.06)]">
              <h3 className="text-sm font-semibold text-white">Line Items</h3>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.04)]">
                  <th className="text-left px-5 py-2 text-xs text-gray-400">Description</th>
                  <th className="text-right px-5 py-2 text-xs text-gray-400">Qty</th>
                  <th className="text-right px-5 py-2 text-xs text-gray-400">Unit Price</th>
                  <th className="text-right px-5 py-2 text-xs text-gray-400">Total</th>
                </tr>
              </thead>
              <tbody>
                {invoice.line_items.map((item, i) => (
                  <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                    <td className="px-5 py-3">
                      <p className="text-sm text-white">{item.description}</p>
                      <p className="text-xs text-gray-500">{item.item_code}</p>
                    </td>
                    <td className="px-5 py-3 text-sm text-gray-300 text-right">{item.qty}</td>
                    <td className="px-5 py-3 text-sm text-gray-300 text-right">{formatCurrency(item.unit_price)}</td>
                    <td className="px-5 py-3 text-sm text-white text-right font-medium">{formatCurrency(item.line_total)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="border-t border-[rgba(255,255,255,0.06)]">
                  <td colSpan={3} className="px-5 py-2 text-sm text-gray-400 text-right">Subtotal</td>
                  <td className="px-5 py-2 text-sm text-white text-right">{formatCurrency(invoice.subtotal)}</td>
                </tr>
                <tr>
                  <td colSpan={3} className="px-5 py-2 text-sm text-gray-400 text-right">VAT (15%)</td>
                  <td className="px-5 py-2 text-sm text-white text-right">{formatCurrency(invoice.vat_amount)}</td>
                </tr>
                <tr className="border-t border-[rgba(255,255,255,0.06)]">
                  <td colSpan={3} className="px-5 py-3 text-sm font-semibold text-white text-right">Total</td>
                  <td className="px-5 py-3 text-lg font-bold text-white text-right">{formatCurrency(invoice.total)}</td>
                </tr>
                {invoice.amount_paid > 0 && (
                  <>
                    <tr>
                      <td colSpan={3} className="px-5 py-2 text-sm text-green-400 text-right">Paid</td>
                      <td className="px-5 py-2 text-sm text-green-400 text-right">-{formatCurrency(invoice.amount_paid)}</td>
                    </tr>
                    <tr className="border-t border-[rgba(255,255,255,0.06)]">
                      <td colSpan={3} className="px-5 py-3 text-sm font-semibold text-yellow-400 text-right">Balance Due</td>
                      <td className="px-5 py-3 text-lg font-bold text-yellow-400 text-right">{formatCurrency(invoice.balance_due)}</td>
                    </tr>
                  </>
                )}
              </tfoot>
            </table>
          </div>

          {invoice.notes && (
            <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5">
              <h3 className="text-sm font-semibold text-white mb-2">Notes</h3>
              <p className="text-sm text-gray-400">{invoice.notes}</p>
            </div>
          )}
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Customer Info */}
          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-3">
            <h3 className="text-sm font-semibold text-white">Customer</h3>
            <div className="space-y-2">
              <p className="text-sm text-white">{invoice.acct_customers?.legal_name}</p>
              {invoice.acct_customers?.email && (
                <p className="text-xs text-gray-400">{invoice.acct_customers.email}</p>
              )}
              {invoice.acct_customers?.phone && (
                <p className="text-xs text-gray-400">{invoice.acct_customers.phone}</p>
              )}
              {invoice.acct_customers?.billing_address && (
                <p className="text-xs text-gray-400">{invoice.acct_customers.billing_address}</p>
              )}
            </div>
          </div>

          {/* Activity Timeline */}
          <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5">
            <h3 className="text-sm font-semibold text-white mb-4">Activity</h3>
            {auditLog.length === 0 ? (
              <p className="text-xs text-gray-500">No activity yet</p>
            ) : (
              <div className="space-y-3">
                {auditLog.map((entry) => (
                  <div key={entry.id} className="flex gap-3">
                    <div className="mt-0.5">
                      <Clock size={14} className="text-gray-500" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs text-white">
                        {entry.event_type.replace(/_/g, " ")}
                      </p>
                      <p className="text-xs text-gray-500">
                        {entry.actor} &middot; {formatDateTime(entry.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
