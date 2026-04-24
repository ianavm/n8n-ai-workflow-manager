"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { FileText } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { DataTable, type DataTableColumn } from "@/components/ui-shadcn/data-table";
import { InvoiceStatusBadge } from "@/components/accounting/InvoiceStatusBadge";
import { useRouter } from "next/navigation";

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
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export default function ClientInvoiceListPage() {
  const router = useRouter();
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

  const columns: DataTableColumn<Invoice>[] = [
    {
      key: "invoice_number",
      header: "Invoice",
      cell: (inv) => (
        <Link
          href={`/portal/accounting/invoices/${inv.id}`}
          className="font-medium text-[var(--brand-primary)] hover:underline"
        >
          {inv.invoice_number}
        </Link>
      ),
    },
    {
      key: "total",
      header: "Total",
      align: "right",
      cell: (inv) => <span className="tabular-nums">{formatCurrency(inv.total)}</span>,
    },
    {
      key: "balance_due",
      header: "Balance",
      align: "right",
      cell: (inv) => (
        <span
          className="tabular-nums font-semibold"
          style={{ color: inv.balance_due > 0 ? "var(--warning)" : "var(--accent-teal)" }}
        >
          {formatCurrency(inv.balance_due)}
        </span>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (inv) => <InvoiceStatusBadge status={inv.status} />,
    },
    {
      key: "due_date",
      header: "Due",
      cell: (inv) => <span className="text-[var(--text-muted)]">{formatDate(inv.due_date)}</span>,
    },
  ];

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Finance"
        title="Invoices"
        description="Every invoice issued to your account."
      />

      <DataTable
        columns={columns}
        data={invoices}
        rowKey="id"
        loading={loading}
        onRowClick={(row) => router.push(`/portal/accounting/invoices/${row.id}`)}
        emptyState={
          <EmptyState
            inline
            icon={<FileText className="size-5" />}
            title="No invoices"
            description="Invoices will appear here once issued."
          />
        }
      />
    </div>
  );
}
