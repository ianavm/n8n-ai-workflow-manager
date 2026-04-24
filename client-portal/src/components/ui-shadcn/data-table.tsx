"use client";

import * as React from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight } from "lucide-react";

import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui-shadcn/table";
import { Skeleton } from "@/components/ui-shadcn/skeleton";
import { Button } from "@/components/ui-shadcn/button";

export type ColumnAlign = "left" | "center" | "right";

export interface DataTableColumn<T> {
  key: string;
  header: React.ReactNode;
  /** Render cell content. If omitted, renders `row[key as keyof T]` as string. */
  cell?: (row: T, index: number) => React.ReactNode;
  /** Enable sort UI — parent controls sorted state via `sort` + `onSort`. */
  sortable?: boolean;
  align?: ColumnAlign;
  width?: string | number;
  className?: string;
}

export interface DataTablePagination {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}

export interface DataTableSort {
  key: string;
  direction: "asc" | "desc";
}

export interface DataTableProps<T> {
  columns: DataTableColumn<T>[];
  data: T[];
  /** Stable key for each row — string accessor or property. Defaults to `id`. */
  rowKey?: keyof T | ((row: T, index: number) => string | number);
  onRowClick?: (row: T, index: number) => void;
  emptyState?: React.ReactNode;
  loading?: boolean;
  loadingRows?: number;
  pagination?: DataTablePagination;
  sort?: DataTableSort | null;
  onSort?: (next: DataTableSort | null) => void;
  className?: string;
  caption?: React.ReactNode;
}

const alignClass: Record<ColumnAlign, string> = {
  left: "text-left",
  center: "text-center",
  right: "text-right",
};

function resolveKey<T>(
  row: T,
  index: number,
  rowKey: DataTableProps<T>["rowKey"],
): string | number {
  if (typeof rowKey === "function") return rowKey(row, index);
  if (rowKey) return String((row as Record<string, unknown>)[rowKey as string] ?? index);
  const maybeId = (row as Record<string, unknown>).id;
  return typeof maybeId === "string" || typeof maybeId === "number" ? maybeId : index;
}

function SortIndicator({ direction }: { direction: "asc" | "desc" | null }) {
  if (direction === "asc") return <ArrowUp className="size-3.5" aria-hidden />;
  if (direction === "desc") return <ArrowDown className="size-3.5" aria-hidden />;
  return <ArrowUpDown className="size-3.5 opacity-50" aria-hidden />;
}

export function DataTable<T>({
  columns,
  data,
  rowKey,
  onRowClick,
  emptyState,
  loading = false,
  loadingRows = 5,
  pagination,
  sort,
  onSort,
  className,
  caption,
}: DataTableProps<T>) {
  const isEmpty = !loading && data.length === 0;
  const totalPages = pagination
    ? Math.max(1, Math.ceil(pagination.total / pagination.pageSize))
    : 0;

  const handleSort = React.useCallback(
    (key: string) => {
      if (!onSort) return;
      const currentDir = sort?.key === key ? sort.direction : null;
      const nextDir = currentDir === "asc" ? "desc" : currentDir === "desc" ? null : "asc";
      onSort(nextDir ? { key, direction: nextDir } : null);
    },
    [onSort, sort],
  );

  return (
    <div className={cn("flex flex-col gap-3", className)}>
      <Table>
        {caption ? <caption className="sr-only">{caption}</caption> : null}
        <TableHeader>
          <TableRow>
            {columns.map((col) => {
              const isSorted = sort?.key === col.key;
              const dir = isSorted ? sort.direction : null;
              return (
                <TableHead
                  key={col.key}
                  style={col.width ? { width: col.width } : undefined}
                  className={cn(alignClass[col.align ?? "left"], col.className)}
                >
                  {col.sortable && onSort ? (
                    <button
                      type="button"
                      onClick={() => handleSort(col.key)}
                      className={cn(
                        "inline-flex items-center gap-1.5 uppercase tracking-[0.1em]",
                        "transition-colors hover:text-foreground",
                        isSorted && "text-foreground",
                      )}
                    >
                      {col.header}
                      <SortIndicator direction={dir} />
                    </button>
                  ) : (
                    col.header
                  )}
                </TableHead>
              );
            })}
          </TableRow>
        </TableHeader>

        <TableBody>
          {loading ? (
            Array.from({ length: loadingRows }).map((_, rowIndex) => (
              <TableRow key={`skeleton-${rowIndex}`}>
                {columns.map((col) => (
                  <TableCell key={col.key} className={alignClass[col.align ?? "left"]}>
                    <Skeleton className="h-4 w-full max-w-[200px]" />
                  </TableCell>
                ))}
              </TableRow>
            ))
          ) : isEmpty ? (
            <TableRow>
              <TableCell colSpan={columns.length} className="text-center py-16">
                {emptyState ?? (
                  <span className="text-sm text-[var(--text-muted)]">No results.</span>
                )}
              </TableCell>
            </TableRow>
          ) : (
            data.map((row, index) => (
              <TableRow
                key={resolveKey(row, index, rowKey)}
                onClick={onRowClick ? () => onRowClick(row, index) : undefined}
                className={onRowClick ? "cursor-pointer" : undefined}
                data-state={undefined}
              >
                {columns.map((col) => {
                  const content = col.cell
                    ? col.cell(row, index)
                    : (row as Record<string, unknown>)[col.key];
                  return (
                    <TableCell
                      key={col.key}
                      className={cn(alignClass[col.align ?? "left"], col.className)}
                    >
                      {content as React.ReactNode}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {pagination && pagination.total > pagination.pageSize ? (
        <div className="flex items-center justify-between gap-3 px-1">
          <p className="text-xs text-[var(--text-muted)]">
            Page <span className="font-semibold text-foreground">{pagination.page}</span> of{" "}
            <span className="font-semibold text-foreground">{totalPages}</span>
            <span className="mx-2">·</span>
            {pagination.total} total
          </p>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page <= 1}
              onClick={() => pagination.onPageChange(pagination.page - 1)}
              aria-label="Previous page"
            >
              <ChevronLeft className="size-3.5" />
              Prev
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={pagination.page >= totalPages}
              onClick={() => pagination.onPageChange(pagination.page + 1)}
              aria-label="Next page"
            >
              Next
              <ChevronRight className="size-3.5" />
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
