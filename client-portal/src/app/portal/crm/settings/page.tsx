import { redirect } from "next/navigation";
import { Settings as SettingsIcon } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { CardShell } from "@/components/crm/CardShell";
import { EmptyState } from "@/components/crm/EmptyState";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) redirect("/portal/crm");

  const supabase = await createServerSupabaseClient();
  const { data: config } = await supabase
    .from("crm_config")
    .select("*")
    .eq("client_id", clientId)
    .maybeSingle();

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="CRM preferences scoped to your organization. Read-only in Phase 1 — editing ships with admin self-serve in Phase 2."
      />

      {!config ? (
        <CardShell>
          <EmptyState
            icon={SettingsIcon}
            title="Not configured yet"
            description="Your AVM admin will configure your sender identity and scoring weights in the next setup pass."
          />
        </CardShell>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          <CardShell title="Sender Identity">
            <dl className="space-y-3 text-sm">
              <KV label="Sender name">{config.sender_name ?? "—"}</KV>
              <KV label="Sender email">{config.sender_email ?? "—"}</KV>
              <KV label="Signature">
                <pre className="whitespace-pre-wrap font-sans text-[#B0B8C8]">
                  {config.sender_signature ?? "—"}
                </pre>
              </KV>
            </dl>
          </CardShell>

          <CardShell title="Scoring Weights">
            <ul className="space-y-2.5 text-sm">
              <WeightRow label="ICP fit" value={config.score_weight_icp_fit} />
              <WeightRow label="Buying signals" value={config.score_weight_signals} />
              <WeightRow label="Engagement recency" value={config.score_weight_recency} />
              <WeightRow label="Data completeness" value={config.score_weight_completeness} />
            </ul>
          </CardShell>

          <CardShell title="Airtable Reconcile">
            <dl className="space-y-3 text-sm">
              <KV label="Enabled">{config.airtable_sync_enabled ? "Yes" : "No"}</KV>
              <KV label="Base ID">{config.airtable_base_id ?? "—"}</KV>
              <KV label="Companies table">{config.airtable_companies_table ?? "—"}</KV>
              <KV label="Leads table">{config.airtable_leads_table ?? "—"}</KV>
            </dl>
          </CardShell>

          <CardShell title="Regional">
            <dl className="space-y-3 text-sm">
              <KV label="Timezone">{config.timezone}</KV>
              <KV label="Accent color">
                {config.accent_color ? (
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="w-4 h-4 rounded border border-[rgba(255,255,255,0.1)]"
                      style={{ background: config.accent_color }}
                    />
                    {config.accent_color}
                  </span>
                ) : (
                  "Default (AVM orange)"
                )}
              </KV>
            </dl>
          </CardShell>
        </div>
      )}
    </div>
  );
}

function KV({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[11px] uppercase tracking-wider text-[#71717A]">{label}</dt>
      <dd className="text-[#E4E4E7] mt-0.5">{children}</dd>
    </div>
  );
}

function WeightRow({ label, value }: { label: string; value: number }) {
  return (
    <li className="flex items-center justify-between gap-3">
      <span className="text-[#B0B8C8]">{label}</span>
      <div className="flex items-center gap-2">
        <div className="w-24 h-1.5 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
          <div
            className="h-full rounded-full"
            style={{ width: `${value}%`, background: "#FF6D5A" }}
          />
        </div>
        <span className="text-xs text-white tabular-nums w-10 text-right">{value}%</span>
      </div>
    </li>
  );
}
