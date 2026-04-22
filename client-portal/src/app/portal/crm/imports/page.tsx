import Link from "next/link";
import { redirect } from "next/navigation";
import { Upload } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { EmptyState } from "@/components/crm/EmptyState";
import { CardShell } from "@/components/crm/CardShell";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

export const dynamic = "force-dynamic";

interface ImportRow {
  id: string;
  filename: string;
  status: string;
  rows_total: number | null;
  rows_ingested: number;
  rows_failed: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

function fmt(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-ZA", { dateStyle: "medium", timeStyle: "short" });
}

export default async function ImportsPage() {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) redirect("/portal/crm");

  const supabase = await createServerSupabaseClient();
  const { data } = await supabase
    .from("crm_imports")
    .select("id, filename, status, rows_total, rows_ingested, rows_failed, error_message, created_at, completed_at")
    .eq("client_id", clientId)
    .order("created_at", { ascending: false })
    .limit(50);

  const rows = (data ?? []) as ImportRow[];

  return (
    <div className="space-y-6">
      <PageHeader
        title="Imports"
        description="Bring your existing CRM (HubSpot, Pipedrive, Salesforce, Zoho, Apollo, or anywhere else) into this dashboard via CSV."
        action={
          <Link
            href="/portal/crm/imports/new"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-[rgba(255,109,90,0.35)] bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.22)] transition-colors"
          >
            <Upload size={14} />
            Import CSV
          </Link>
        }
      />

      {rows.length === 0 ? (
        <CardShell>
          <EmptyState
            icon={Upload}
            title="No imports yet"
            description="Click 'Import CSV' above to bring leads in from your existing CRM. We auto-detect common column names — you just confirm the mapping."
            primaryAction={
              <Link
                href="/portal/crm/imports/new"
                className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-[rgba(255,109,90,0.35)] bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.22)] transition-colors"
              >
                <Upload size={14} />
                Import your first CSV
              </Link>
            }
          />
        </CardShell>
      ) : (
        <CardShell padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-[#71717A] border-b border-[rgba(255,255,255,0.05)]">
                  <th className="px-5 py-3 font-medium">File</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Rows</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                  <th className="px-5 py-3 font-medium">Completed</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.id} className="border-b border-[rgba(255,255,255,0.04)]">
                    <td className="px-5 py-3 text-white">{r.filename}</td>
                    <td className="px-5 py-3">
                      <span
                        className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium border"
                        style={statusStyle(r.status)}
                      >
                        {r.status}
                      </span>
                      {r.error_message && (
                        <div className="text-[11px] text-red-400 mt-1 max-w-xs truncate" title={r.error_message}>
                          {r.error_message}
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-3 tabular-nums text-[#B0B8C8]">
                      {r.rows_ingested}/{r.rows_total ?? "?"}
                      {r.rows_failed > 0 && (
                        <span className="ml-2 text-red-400">({r.rows_failed} failed)</span>
                      )}
                    </td>
                    <td className="px-5 py-3 text-[#B0B8C8]">{fmt(r.created_at)}</td>
                    <td className="px-5 py-3 text-[#B0B8C8]">{fmt(r.completed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardShell>
      )}
    </div>
  );
}

function statusStyle(status: string): React.CSSProperties {
  const c =
    status === "completed"
      ? "#10B981"
      : status === "failed"
        ? "#EF4444"
        : status === "ingesting" || status === "parsing"
          ? "#F59E0B"
          : "#71717A";
  return { color: c, borderColor: `${c}55`, background: `${c}15` };
}
