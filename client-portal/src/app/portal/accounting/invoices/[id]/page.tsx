"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, CreditCard, FileText, Upload } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui-shadcn/table";

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
    year: "numeric",
    month: "short",
    day: "numeric",
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

  if (loading) return <LoadingState variant="card" rows={6} />;

  if (!invoice) {
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/portal/accounting/invoices">
            <ArrowLeft className="size-3.5" />
            Back to invoices
          </Link>
        </Button>
        <EmptyState
          icon={<FileText className="size-5" />}
          title="Invoice not found"
          description="The invoice you're looking for may have been removed or is still being prepared."
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link href="/portal/accounting/invoices" className="gap-1.5">
          <ArrowLeft className="size-3.5" />
          Back to invoices
        </Link>
      </Button>

      <PageHeader
        eyebrow="Finance · Invoice"
        title={invoice.invoice_number}
        description={`Due ${formatDate(invoice.due_date)}`}
        actions={<InvoiceStatusBadge status={invoice.status} />}
      />

      {/* Payment banner */}
      {invoice.balance_due > 0 ? (
        <Card
          variant="default"
          accent="coral"
          padding="lg"
          className="border-[color-mix(in_srgb,var(--accent-coral)_30%,transparent)] bg-[color-mix(in_srgb,var(--accent-coral)_6%,transparent)]"
        >
          <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-foreground">
                Balance due: <span className="gradient-text-coral">{formatCurrency(invoice.balance_due)}</span>
              </p>
              <p className="text-sm text-[var(--text-muted)] mt-1">
                Pay online or upload proof of payment.
              </p>
            </div>
            <div className="flex gap-2">
              {invoice.payment_link ? (
                <Button asChild variant="default">
                  <a href={invoice.payment_link} target="_blank" rel="noopener noreferrer">
                    <CreditCard className="size-4" />
                    Pay now
                  </a>
                </Button>
              ) : null}
              <Button variant="outline">
                <Upload className="size-4" />
                Upload POP
              </Button>
            </div>
          </div>
        </Card>
      ) : null}

      {/* Line items */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Line items</CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Description</TableHead>
                <TableHead className="text-right">Qty</TableHead>
                <TableHead className="text-right">Price</TableHead>
                <TableHead className="text-right">Total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {invoice.line_items.map((item, i) => (
                <TableRow key={i}>
                  <TableCell className="font-medium text-foreground">{item.description}</TableCell>
                  <TableCell className="text-right text-[var(--text-muted)]">{item.qty}</TableCell>
                  <TableCell className="text-right text-[var(--text-muted)] tabular-nums">
                    {formatCurrency(item.unit_price)}
                  </TableCell>
                  <TableCell className="text-right font-semibold tabular-nums">
                    {formatCurrency(item.line_total)}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell colSpan={3} className="text-right text-[var(--text-muted)]">
                  Subtotal
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(invoice.subtotal)}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell colSpan={3} className="text-right text-[var(--text-muted)]">
                  VAT
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(invoice.vat_amount)}
                </TableCell>
              </TableRow>
              <TableRow>
                <TableCell colSpan={3} className="text-right font-semibold text-foreground">
                  Total
                </TableCell>
                <TableCell className="text-right text-lg font-bold text-foreground tabular-nums">
                  {formatCurrency(invoice.total)}
                </TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </CardContent>
      </Card>

      {invoice.pdf_url ? (
        <Button asChild variant="outline" size="sm" className="self-start">
          <a href={invoice.pdf_url} target="_blank" rel="noopener noreferrer">
            <FileText className="size-3.5" />
            Download PDF
          </a>
        </Button>
      ) : null}
    </div>
  );
}
