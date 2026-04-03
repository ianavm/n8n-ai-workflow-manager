"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { FileText, ArrowLeft, CreditCard, Upload } from "lucide-react";
import Link from "next/link";

interface LineItem {
  description: string;
  qty: number;
  unit_price: number;
  line_total: number;
}

interface Invoice {
  id: string;
  invoice_number: string;
  issue_date: string;
  due_date: string;
  status: string;
  subtotal: number;
  vat_amount: number;
  total: number;
  amount_paid: number;
  balance_due: number;
  line_items: LineItem[];
  pdf_url: string | null;
  payment_link: string | null;
  notes: string | null;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    year: "numeric", month: "short", day: "numeric",
  });
}

export default function ClientInvoiceDetailPage() {
  const params = useParams();
  const invoiceId = params.id as string;
  const supabase = createClient();
  const [invoice, setInvoice] = useState<Invoice | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from("acct_invoices")
        .select("*")
        .eq("id", invoiceId)
        .single();
      if (data) setInvoice(data as Invoice);
      setLoading(false);
    }
    load();
  }, [supabase, invoiceId]);

  if (loading) {
    return <div className="h-64 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />;
  }

  if (!invoice) {
    return (
      <div className="text-center py-12">
        <FileText className="mx-auto mb-4 text-gray-600" size={48} />
        <p className="text-gray-400">Invoice not found</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/portal/accounting/invoices" className="text-gray-400 hover:text-white">
          <ArrowLeft size={20} />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-white">{invoice.invoice_number}</h1>
          <p className="text-sm text-gray-400">Due: {formatDate(invoice.due_date)}</p>
        </div>
        <InvoiceStatusBadge status={invoice.status} />
      </div>

      {/* Payment Actions */}
      {invoice.balance_due > 0 && (
        <div className="rounded-xl border border-[rgba(255,109,90,0.3)] bg-[rgba(255,109,90,0.05)] p-5 flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-white">Balance Due: {formatCurrency(invoice.balance_due)}</p>
            <p className="text-xs text-gray-400">Pay online or upload proof of payment</p>
          </div>
          <div className="flex gap-2">
            {invoice.payment_link && (
              <a
                href={invoice.payment_link}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF6D5A] text-white text-sm font-medium hover:bg-[#e85d4a]"
              >
                <CreditCard size={16} /> Pay Now
              </a>
            )}
            <button className="flex items-center gap-2 px-4 py-2 rounded-lg border border-[rgba(255,255,255,0.1)] text-white text-sm hover:bg-[rgba(255,255,255,0.05)]">
              <Upload size={16} /> Upload POP
            </button>
          </div>
        </div>
      )}

      {/* Line Items */}
      <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              <th className="text-left px-5 py-3 text-xs text-gray-400">Description</th>
              <th className="text-right px-5 py-3 text-xs text-gray-400">Qty</th>
              <th className="text-right px-5 py-3 text-xs text-gray-400">Price</th>
              <th className="text-right px-5 py-3 text-xs text-gray-400">Total</th>
            </tr>
          </thead>
          <tbody>
            {invoice.line_items.map((item, i) => (
              <tr key={i} className="border-b border-[rgba(255,255,255,0.03)]">
                <td className="px-5 py-3 text-sm text-white">{item.description}</td>
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
              <td colSpan={3} className="px-5 py-2 text-sm text-gray-400 text-right">VAT</td>
              <td className="px-5 py-2 text-sm text-white text-right">{formatCurrency(invoice.vat_amount)}</td>
            </tr>
            <tr className="border-t border-[rgba(255,255,255,0.06)]">
              <td colSpan={3} className="px-5 py-3 text-sm font-semibold text-white text-right">Total</td>
              <td className="px-5 py-3 text-lg font-bold text-white text-right">{formatCurrency(invoice.total)}</td>
            </tr>
          </tfoot>
        </table>
      </div>

      {invoice.pdf_url && (
        <a
          href={invoice.pdf_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 text-sm text-[#FF6D5A] hover:underline"
        >
          <FileText size={14} /> Download PDF
        </a>
      )}
    </div>
  );
}
