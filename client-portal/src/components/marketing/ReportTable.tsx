"use client";

import { useState, useMemo, useCallback } from "react";
import { ChevronUp, ChevronDown, ChevronsUpDown } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Format Helpers                                                      */
/* ------------------------------------------------------------------ */

export function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

export function formatNumber(n: number): string {
  return n.toLocaleString("en-ZA");
}

export function formatPercent(n: number): string {
  return `${n.toFixed(2)}%`;
}

type FormatFn = "zar" | "number" | "percent" | "date" | undefined;

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export interface ColumnDef {
  key: string;
  label: string;
  format?: FormatFn;
  align?: "left" | "right";
}

interface ReportTableProps {
  data: ReadonlyArray<Record<string, unknown>>;
  columns: ReadonlyArray<ColumnDef>;
}

type SortDir = "asc" | "desc" | null;

/* ------------------------------------------------------------------ */
/* Component                                                           */
/* ------------------------------------------------------------------ */

export function ReportTable({ data, columns }: ReportTableProps) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);

  const handleSort = useCallback(
    (key: string) => {
      if (sortKey === key) {
        if (sortDir === "asc") {
          setSortDir("desc");
        } else if (sortDir === "desc") {
          setSortKey(null);
          setSortDir(null);
        }
      } else {
        setSortKey(key);
        setSortDir("asc");
      }
    },
    [sortKey, sortDir]
  );

  const sortedData = useMemo(() => {
    if (!sortKey || !sortDir) return [...data];

    return [...data].sort((a, b) => {
      const aVal = a[sortKey];
      const bVal = b[sortKey];

      if (aVal == null && bVal == null) return 0;
      if (aVal == null) return 1;
      if (bVal == null) return -1;

      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc"
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal);
      }

      const numA = Number(aVal);
      const numB = Number(bVal);
      return sortDir === "asc" ? numA - numB : numB - numA;
    });
  }, [data, sortKey, sortDir]);

  const totals = useMemo(() => {
    const result: Record<string, number> = {};
    for (const col of columns) {
      if (col.format === "date" || col.key === "date") continue;
      const values = data
        .map((row) => row[col.key])
        .filter((v): v is number => typeof v === "number");

      if (values.length > 0) {
        if (col.format === "percent") {
          result[col.key] = values.reduce((s, v) => s + v, 0) / values.length;
        } else {
          result[col.key] = values.reduce((s, v) => s + v, 0);
        }
      }
    }
    return result;
  }, [data, columns]);

  function formatCell(value: unknown, format: FormatFn): string {
    if (value == null) return "-";
    switch (format) {
      case "zar":
        return formatZAR(Number(value));
      case "number":
        return formatNumber(Number(value));
      case "percent":
        return formatPercent(Number(value));
      case "date": {
        const d = new Date(String(value));
        return d.toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric" });
      }
      default:
        return String(value);
    }
  }

  function SortIcon({ columnKey }: { columnKey: string }) {
    if (sortKey !== columnKey) {
      return <ChevronsUpDown size={14} className="text-[#4B5563]" />;
    }
    return sortDir === "asc" ? (
      <ChevronUp size={14} className="text-[#10B981]" />
    ) : (
      <ChevronDown size={14} className="text-[#10B981]" />
    );
  }

  return (
    <div className="floating-card overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-[rgba(255,255,255,0.06)]">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className="px-4 py-3 text-[#6B7280] font-medium cursor-pointer select-none hover:text-[#B0B8C8] transition-colors"
                  style={{ textAlign: col.align ?? (col.format && col.format !== "date" ? "right" : "left") }}
                  onClick={() => handleSort(col.key)}
                >
                  <span className="inline-flex items-center gap-1">
                    {col.label}
                    <SortIcon columnKey={col.key} />
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedData.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-12 text-center text-[#6B7280]"
                >
                  No data available for the selected period.
                </td>
              </tr>
            ) : (
              sortedData.map((row, idx) => (
                <tr
                  key={idx}
                  className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                >
                  {columns.map((col) => (
                    <td
                      key={col.key}
                      className="px-4 py-3 text-[#B0B8C8]"
                      style={{ textAlign: col.align ?? (col.format && col.format !== "date" ? "right" : "left") }}
                    >
                      {formatCell(row[col.key], col.format)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
          {sortedData.length > 0 && (
            <tfoot>
              <tr className="border-t border-[rgba(255,255,255,0.08)] bg-[rgba(255,255,255,0.02)]">
                {columns.map((col, idx) => (
                  <td
                    key={col.key}
                    className="px-4 py-3 text-white font-semibold"
                    style={{ textAlign: col.align ?? (col.format && col.format !== "date" ? "right" : "left") }}
                  >
                    {idx === 0
                      ? "Totals"
                      : totals[col.key] != null
                        ? formatCell(totals[col.key], col.format)
                        : ""}
                  </td>
                ))}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
}
