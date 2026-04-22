import { redirect } from "next/navigation";
import { KanbanSquare } from "lucide-react";
import Link from "next/link";
import { PageHeader } from "@/components/crm/PageHeader";
import { EmptyState } from "@/components/crm/EmptyState";
import { CardShell } from "@/components/crm/CardShell";
import { StatusPill } from "@/components/crm/StatusPill";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

export const dynamic = "force-dynamic";

interface ColumnLead {
  id: string;
  company: { name: string | null } | null;
  contact: { first_name: string | null; last_name: string | null } | null;
  score: number | null;
  deal_value_zar: number | null;
}

interface StageColumn {
  key: string;
  label: string;
  color: string | null;
  leads: ColumnLead[];
  totalValue: number;
}

async function loadBoard(clientId: string): Promise<StageColumn[]> {
  const supabase = await createServerSupabaseClient();

  const [{ data: stages }, { data: leads }] = await Promise.all([
    supabase
      .from("crm_stages")
      .select("key, label, color, order_index")
      .eq("client_id", clientId)
      .order("order_index"),
    supabase
      .from("crm_leads")
      .select(
        `
          id, stage_key, score, deal_value_zar,
          company:crm_companies ( name ),
          contact:crm_contacts ( first_name, last_name )
        `,
      )
      .eq("client_id", clientId)
      .order("updated_at", { ascending: false })
      .limit(500),
  ]);

  const byStage = new Map<string, ColumnLead[]>();
  for (const l of leads ?? []) {
    const key = l.stage_key as string;
    if (!byStage.has(key)) byStage.set(key, []);
    byStage.get(key)!.push(l as unknown as ColumnLead);
  }

  return (stages ?? []).map((s) => {
    const list = byStage.get(s.key) ?? [];
    return {
      key: s.key,
      label: s.label,
      color: s.color ?? null,
      leads: list,
      totalValue: list.reduce((acc, r) => acc + Number(r.deal_value_zar ?? 0), 0),
    };
  });
}

export default async function PipelinePage() {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) redirect("/portal/crm");

  const columns = await loadBoard(clientId);
  const hasAny = columns.some((c) => c.leads.length > 0);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline"
        description="Read-only kanban for now. Drag-to-move will ship in the next iteration."
      />

      {!hasAny ? (
        <CardShell>
          <EmptyState
            icon={KanbanSquare}
            title="No leads in any stage yet"
            description="Once leads flow in they'll appear here grouped by stage."
          />
        </CardShell>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {columns.map((col) => (
            <div
              key={col.key}
              className="min-w-[280px] w-[280px] flex-shrink-0 rounded-xl border bg-[#121827] border-[rgba(255,255,255,0.07)]"
            >
              <div className="px-4 py-3 border-b border-[rgba(255,255,255,0.05)] flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <StatusPill label={col.label} color={col.color ?? "#71717A"} />
                  <span className="text-xs text-[#71717A] tabular-nums">{col.leads.length}</span>
                </div>
                {col.totalValue > 0 && (
                  <span className="text-[11px] text-[#B0B8C8] tabular-nums">
                    R{(col.totalValue / 1000).toFixed(0)}k
                  </span>
                )}
              </div>

              <div className="p-2 space-y-2 max-h-[70vh] overflow-y-auto">
                {col.leads.map((lead) => {
                  const contact =
                    [lead.contact?.first_name, lead.contact?.last_name].filter(Boolean).join(" ") || null;
                  return (
                    <Link
                      key={lead.id}
                      href={`/portal/crm/leads/${lead.id}`}
                      className="block px-3 py-2.5 rounded-lg bg-[#0A0F1A] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,109,90,0.3)] transition-colors"
                    >
                      <div className="text-sm font-medium text-white truncate">
                        {lead.company?.name ?? "Unknown company"}
                      </div>
                      {contact && <div className="text-xs text-[#B0B8C8] mt-0.5 truncate">{contact}</div>}
                      <div className="mt-2 flex items-center justify-between text-[11px] text-[#71717A]">
                        {lead.score !== null && <span>Score {lead.score}</span>}
                        {lead.deal_value_zar && (
                          <span className="tabular-nums">
                            R{(Number(lead.deal_value_zar) / 1000).toFixed(0)}k
                          </span>
                        )}
                      </div>
                    </Link>
                  );
                })}
                {col.leads.length === 0 && (
                  <div className="text-center text-xs text-[#71717A] py-6">No leads</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
