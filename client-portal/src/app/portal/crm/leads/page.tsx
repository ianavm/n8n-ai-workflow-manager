import Link from "next/link";
import { redirect } from "next/navigation";
import { Filter, Search, Users } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { EmptyState } from "@/components/crm/EmptyState";
import { StatusPill } from "@/components/crm/StatusPill";
import { CardShell } from "@/components/crm/CardShell";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import type { CrmLead, CrmCompany, CrmContact, CrmStage } from "@/lib/crm/types";

export const dynamic = "force-dynamic";

interface SearchParams {
  page?: string;
  q?: string;
  stage?: string;
}

interface LeadRow extends CrmLead {
  company: Pick<CrmCompany, "name" | "industry" | "country" | "logo_url"> | null;
  contact: Pick<CrmContact, "first_name" | "last_name" | "email" | "title"> | null;
}

const PAGE_SIZE = 50;

async function loadLeads(clientId: string, params: SearchParams) {
  const supabase = await createServerSupabaseClient();
  const page = Math.max(1, Number(params.page ?? "1"));
  const from = (page - 1) * PAGE_SIZE;
  const to = from + PAGE_SIZE - 1;

  let query = supabase
    .from("crm_leads")
    .select(
      `
        id, stage_key, score, status_tags, tags, source, created_at, updated_at,
        last_touch_at, deal_value_zar,
        company:crm_companies ( name, industry, country, logo_url ),
        contact:crm_contacts ( first_name, last_name, email, title )
      `,
      { count: "exact" },
    )
    .eq("client_id", clientId)
    .order("created_at", { ascending: false })
    .range(from, to);

  if (params.q) {
    query = query.ilike("crm_companies.name", `%${params.q}%`);
  }
  if (params.stage) {
    query = query.eq("stage_key", params.stage);
  }

  const { data, count, error } = await query;
  if (error) throw error;

  const { data: stages } = await supabase
    .from("crm_stages")
    .select("key, label, color")
    .eq("client_id", clientId)
    .order("order_index");

  return {
    rows: (data ?? []) as unknown as LeadRow[],
    total: count ?? 0,
    page,
    stages: (stages ?? []) as Pick<CrmStage, "key" | "label" | "color">[],
  };
}

export default async function LeadsListPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);

  if (!clientId) {
    return (
      <div className="space-y-6">
        <PageHeader title="Leads" description="Pass ?client=<uuid> to scope." />
        <EmptyState icon={Users} title="Select a client" description="Admin view requires a client_id override in this Phase 1 build." />
      </div>
    );
  }

  const params = await searchParams;
  const { rows, total, page, stages } = await loadLeads(clientId, params);
  const stageMap = new Map(stages.map((s) => [s.key, s]));
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <PageHeader
        title="Leads"
        description={`${total.toLocaleString()} leads in your pipeline`}
      />

      <form action="/portal/crm/leads" method="GET" className="flex items-center gap-2">
        <div className="relative flex-1 max-w-md">
          <Search
            size={14}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[#71717A] pointer-events-none"
          />
          <input
            name="q"
            defaultValue={params.q ?? ""}
            placeholder="Search companies…"
            className="w-full pl-9 pr-3 py-2 text-sm rounded-lg bg-[#121827] border border-[rgba(255,255,255,0.07)] text-white placeholder:text-[#71717A] focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
          />
        </div>
        <select
          name="stage"
          defaultValue={params.stage ?? ""}
          className="px-3 py-2 text-sm rounded-lg bg-[#121827] border border-[rgba(255,255,255,0.07)] text-white focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
        >
          <option value="">All stages</option>
          {stages.map((s) => (
            <option key={s.key} value={s.key}>
              {s.label}
            </option>
          ))}
        </select>
        <button
          type="submit"
          className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-[rgba(255,109,90,0.3)] bg-[rgba(255,109,90,0.12)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.18)] transition-colors"
        >
          <Filter size={14} />
          Apply
        </button>
      </form>

      {rows.length === 0 ? (
        <CardShell>
          <EmptyState
            icon={Users}
            title={params.q || params.stage ? "No leads match your filters" : "No leads yet"}
            description={
              params.q || params.stage
                ? "Try clearing the search or picking a different stage."
                : "Your AVM team will populate this list once scraping completes. You can also ask them to import a CSV."
            }
          />
        </CardShell>
      ) : (
        <CardShell padded={false}>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-[#71717A] border-b border-[rgba(255,255,255,0.05)]">
                  <th className="px-5 py-3 font-medium">Company</th>
                  <th className="px-5 py-3 font-medium">Contact</th>
                  <th className="px-5 py-3 font-medium">Stage</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Score</th>
                  <th className="px-5 py-3 font-medium">Country</th>
                  <th className="px-5 py-3 font-medium">Email</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => {
                  const stage = stageMap.get(row.stage_key);
                  return (
                    <tr
                      key={row.id}
                      className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                    >
                      <td className="px-5 py-3">
                        <Link href={`/portal/crm/leads/${row.id}`} className="font-medium text-white hover:text-[#FF6D5A]">
                          {row.company?.name ?? "—"}
                        </Link>
                        {row.company?.industry && (
                          <div className="text-xs text-[#71717A] mt-0.5">{row.company.industry}</div>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        {row.contact ? (
                          <>
                            <div className="text-white">
                              {[row.contact.first_name, row.contact.last_name].filter(Boolean).join(" ") || "—"}
                            </div>
                            {row.contact.title && (
                              <div className="text-xs text-[#71717A] mt-0.5">{row.contact.title}</div>
                            )}
                          </>
                        ) : (
                          <span className="text-[#71717A]">—</span>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <StatusPill label={stage?.label ?? row.stage_key} color={stage?.color ?? "#71717A"} />
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap gap-1.5 max-w-[200px]">
                          {row.status_tags.slice(0, 2).map((tag) => (
                            <StatusPill key={tag} label={tag} color="#8B5CF6" />
                          ))}
                          {row.status_tags.length > 2 && (
                            <span className="text-xs text-[#71717A]">+{row.status_tags.length - 2}</span>
                          )}
                        </div>
                      </td>
                      <td className="px-5 py-3">
                        <ScoreBadge value={row.score} />
                      </td>
                      <td className="px-5 py-3 text-[#B0B8C8]">{row.company?.country ?? "—"}</td>
                      <td className="px-5 py-3">
                        {row.contact?.email ? (
                          <a href={`mailto:${row.contact.email}`} className="text-[#38BDF8] hover:underline">
                            {row.contact.email}
                          </a>
                        ) : (
                          <span className="text-[#71717A]">—</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between px-5 py-3 border-t border-[rgba(255,255,255,0.05)] text-xs text-[#71717A]">
            <span>
              Showing {(page - 1) * PAGE_SIZE + 1}–{Math.min(page * PAGE_SIZE, total)} of {total.toLocaleString()}
            </span>
            <div className="flex items-center gap-2">
              <PageLink page={page - 1} disabled={page <= 1} params={params}>
                ← Prev
              </PageLink>
              <span className="text-[#B0B8C8]">
                Page {page} of {pages}
              </span>
              <PageLink page={page + 1} disabled={page >= pages} params={params}>
                Next →
              </PageLink>
            </div>
          </div>
        </CardShell>
      )}
    </div>
  );
}

function ScoreBadge({ value }: { value: number | null }) {
  if (value === null || value === undefined) return <span className="text-[#71717A]">—</span>;
  const color = value >= 70 ? "#10B981" : value >= 40 ? "#F59E0B" : "#71717A";
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
        <div className="h-full rounded-full" style={{ width: `${value}%`, background: color }} />
      </div>
      <span className="text-xs font-medium tabular-nums" style={{ color }}>
        {value}
      </span>
    </div>
  );
}

function PageLink({
  page,
  disabled,
  params,
  children,
}: {
  page: number;
  disabled: boolean;
  params: SearchParams;
  children: React.ReactNode;
}) {
  if (disabled) {
    return <span className="px-3 py-1.5 rounded-md text-[#71717A] opacity-50">{children}</span>;
  }
  const query = new URLSearchParams();
  query.set("page", String(page));
  if (params.q) query.set("q", params.q);
  if (params.stage) query.set("stage", params.stage);
  return (
    <Link
      href={`/portal/crm/leads?${query.toString()}`}
      className="px-3 py-1.5 rounded-md text-white bg-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.08)]"
    >
      {children}
    </Link>
  );
}
