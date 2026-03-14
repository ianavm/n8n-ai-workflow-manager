"use client";

import { Download } from "lucide-react";
import { format } from "date-fns";

interface Invoice {
  id: string;
  invoice_number: string;
  created_at: string;
  amount_due: number;
  vat_amount: number;
  status: "paid" | "open" | "void" | "draft" | "uncollectible";
  paid_at: string | null;
}

interface InvoiceTableProps {
  invoices: Invoice[];
  loading?: boolean;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

const statusStyles: Record<string, { bg: string; color: string }> = {
  paid: { bg: "rgba(0, 212, 170, 0.1)", color: "#00D4AA" },
  open: { bg: "rgba(245, 158, 11, 0.1)", color: "#F59E0B" },
  void: { bg: "rgba(107, 114, 128, 0.1)", color: "#6B7280" },
  draft: { bg: "rgba(107, 114, 128, 0.1)", color: "#6B7280" },
};

function SkeletonRow() {
  return (
    <tr>
      {Array.from({ length: 7 }).map((_, i) => (
        <td
          key={i}
          style={{
            padding: "14px 16px",
            borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
          }}
        >
          <div
            style={{
              height: "14px",
              borderRadius: "6px",
              background: "rgba(255, 255, 255, 0.06)",
              width: i === 6 ? "60px" : "80px",
              animation: "pulse 1.5s ease-in-out infinite",
            }}
          />
        </td>
      ))}
    </tr>
  );
}

export function InvoiceTable({ invoices, loading = false }: InvoiceTableProps) {
  const columns = [
    "Invoice #",
    "Date",
    "Amount (excl. VAT)",
    "VAT (15%)",
    "Total",
    "Status",
    "Actions",
  ];

  return (
    <div
      style={{
        background: "rgba(255, 255, 255, 0.05)",
        border: "1px solid rgba(255, 255, 255, 0.08)",
        borderRadius: "16px",
        overflow: "hidden",
        fontFamily: "Inter, sans-serif",
      }}
    >
      <div style={{ overflowX: "auto" }}>
        <table
          style={{
            width: "100%",
            borderCollapse: "collapse",
            minWidth: "700px",
          }}
        >
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col}
                  style={{
                    padding: "14px 16px",
                    textAlign: "left",
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#6B7280",
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                    borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
                    whiteSpace: "nowrap",
                  }}
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <>
                <SkeletonRow />
                <SkeletonRow />
                <SkeletonRow />
              </>
            ) : invoices.length === 0 ? (
              <tr>
                <td
                  colSpan={7}
                  style={{
                    padding: "48px 16px",
                    textAlign: "center",
                    fontSize: "14px",
                    color: "#6B7280",
                  }}
                >
                  No invoices yet.
                </td>
              </tr>
            ) : (
              invoices.map((inv) => {
                const sts = statusStyles[inv.status] || statusStyles.draft;
                const total = inv.amount_due + inv.vat_amount;
                return (
                  <tr
                    key={inv.id}
                    style={{
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.background =
                        "rgba(255, 255, 255, 0.02)";
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.background = "transparent";
                    }}
                  >
                    <td
                      style={{
                        padding: "14px 16px",
                        fontSize: "14px",
                        color: "#fff",
                        fontWeight: 500,
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      {inv.invoice_number}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        fontSize: "13px",
                        color: "#B0B8C8",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {format(new Date(inv.created_at), "MMM d, yyyy")}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        fontSize: "14px",
                        color: "#fff",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      {formatZAR(inv.amount_due)}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        fontSize: "14px",
                        color: "#B0B8C8",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      {formatZAR(inv.vat_amount)}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        fontSize: "14px",
                        color: "#fff",
                        fontWeight: 600,
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      {formatZAR(total)}
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      <span
                        style={{
                          background: sts.bg,
                          color: sts.color,
                          fontSize: "12px",
                          fontWeight: 600,
                          padding: "4px 10px",
                          borderRadius: "8px",
                          textTransform: "capitalize",
                        }}
                      >
                        {inv.status}
                      </span>
                    </td>
                    <td
                      style={{
                        padding: "14px 16px",
                        borderBottom: "1px solid rgba(255, 255, 255, 0.04)",
                      }}
                    >
                      <button
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          background: "transparent",
                          border: "1px solid rgba(255, 255, 255, 0.1)",
                          color: "#B0B8C8",
                          fontSize: "12px",
                          fontWeight: 500,
                          padding: "6px 12px",
                          borderRadius: "8px",
                          cursor: "pointer",
                          transition: "color 0.2s ease, border-color 0.2s ease",
                          fontFamily: "Inter, sans-serif",
                        }}
                        onMouseEnter={(e) => {
                          e.currentTarget.style.color = "#fff";
                          e.currentTarget.style.borderColor =
                            "rgba(255, 255, 255, 0.2)";
                        }}
                        onMouseLeave={(e) => {
                          e.currentTarget.style.color = "#B0B8C8";
                          e.currentTarget.style.borderColor =
                            "rgba(255, 255, 255, 0.1)";
                        }}
                      >
                        <Download size={13} />
                        Download
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
