import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  ArrowLeft,
  Building2,
  Clock,
  FileText,
  Mail,
  Phone,
  Send,
  Sparkles,
} from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { CardShell } from "@/components/crm/CardShell";
import { StatusPill } from "@/components/crm/StatusPill";
import { EmptyState } from "@/components/crm/EmptyState";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

export const dynamic = "force-dynamic";

interface ActivityRow {
  id: string;
  kind: string;
  meta: Record<string, unknown>;
  created_at: string;
}

interface LeadDetail {
  id: string;
  stage_key: string;
  score: number | null;
  status_tags: string[];
  tags: string[];
  source: string | null;
  source_campaign: string | null;
  next_action: string | null;
  next_action_at: string | null;
  last_touch_at: string | null;
  deal_value_zar: number | null;
  deal_probability: number | null;
  created_at: string;
  updated_at: string;
  company: {
    id: string;
    name: string | null;
    domain: string | null;
    industry: string | null;
    country: string | null;
    size_band: string | null;
    revenue_band: string | null;
    linkedin_url: string | null;
    website: string | null;
    logo_url: string | null;
    hq_city: string | null;
  } | null;
  contact: {
    id: string;
    first_name: string | null;
    last_name: string | null;
    title: string | null;
    email: string | null;
    phone: string | null;
    linkedin_url: string | null;
  } | null;
}

async function loadLead(clientId: string, leadId: string) {
  const supabase = await createServerSupabaseClient();
  const [leadResult, { data: activities }, { data: research }, { data: stages }] =
    await Promise.all([
      supabase
        .from("crm_leads")
        .select(
          `
            id, stage_key, score, status_tags, tags, source, source_campaign,
            next_action, next_action_at, last_touch_at, deal_value_zar, deal_probability,
            created_at, updated_at,
            company:crm_companies ( id, name, domain, industry, country, size_band, revenue_band, linkedin_url, website, logo_url, hq_city ),
            contact:crm_contacts ( id, first_name, last_name, title, email, phone, linkedin_url )
          `,
        )
        .eq("id", leadId)
        .eq("client_id", clientId)
        .maybeSingle(),
      supabase
        .from("crm_activities")
        .select("id, kind, meta, created_at")
        .eq("lead_id", leadId)
        .order("created_at", { ascending: false })
        .limit(50),
      supabase
        .from("crm_research_reports")
        .select("id, summary, sections, doc_url, pdf_url, model, created_at")
        .eq("lead_id", leadId)
        .eq("is_current", true)
        .maybeSingle(),
      supabase
        .from("crm_stages")
        .select("key, label, color")
        .eq("client_id", clientId)
        .order("order_index"),
    ]);

  if (leadResult.error) throw leadResult.error;
  if (!leadResult.data) return null;

  const lead = leadResult.data as unknown as LeadDetail;

  return {
    lead,
    activities: (activities ?? []) as ActivityRow[],
    research,
    stages: stages ?? [],
  };
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-ZA", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function activityLabel(kind: string): string {
  const map: Record<string, string> = {
    created: "Lead created",
    enriched: "Contact enriched",
    researched: "Research generated",
    scored: "Score updated",
    stage_changed: "Stage changed",
    owner_changed: "Owner changed",
    emailed: "Email sent",
    opened: "Email opened",
    clicked: "Link clicked",
    replied: "Reply received",
    call_scheduled: "Call scheduled",
    call_completed: "Call completed",
    note_added: "Note added",
    tag_added: "Tag added",
    tag_removed: "Tag removed",
    won: "Closed won",
    lost: "Closed lost",
  };
  return map[kind] ?? kind;
}

export default async function LeadDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) redirect("/portal/crm");

  const { id } = await params;
  const loaded = await loadLead(clientId, id);
  if (!loaded) notFound();

  const { lead, activities, research, stages } = loaded;
  const stage = stages.find((s) => s.key === lead.stage_key);

  const contactName =
    [lead.contact?.first_name, lead.contact?.last_name].filter(Boolean).join(" ") || "—";

  const composeHref = lead.contact?.email
    ? `/portal/crm/communications?lead=${lead.id}`
    : "/portal/crm/communications";

  return (
    <div className="space-y-6">
      <Link
        href="/portal/crm/leads"
        className="inline-flex items-center gap-1.5 text-xs text-[#B0B8C8] hover:text-white"
      >
        <ArrowLeft size={12} />
        Back to leads
      </Link>

      <PageHeader
        title={lead.company?.name ?? "Unknown company"}
        description={contactName}
        action={
          <div className="flex items-center gap-2">
            <StatusPill label={stage?.label ?? lead.stage_key} color={stage?.color ?? "#71717A"} size="md" />
            <Link
              href={composeHref}
              className="inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg border border-[rgba(255,109,90,0.3)] bg-[rgba(255,109,90,0.12)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.18)] transition-colors"
            >
              <Send size={14} />
              Compose
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
        <div className="xl:col-span-3 space-y-5">
          <CardShell title="Lead Info">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <KV label="Contact">{contactName}</KV>
              <KV label="Title">{lead.contact?.title ?? "—"}</KV>
              <KV label="Email">
                {lead.contact?.email ? (
                  <a href={`mailto:${lead.contact.email}`} className="text-[#38BDF8] hover:underline">
                    {lead.contact.email}
                  </a>
                ) : (
                  "—"
                )}
              </KV>
              <KV label="Phone">{lead.contact?.phone ?? "—"}</KV>
              <KV label="LinkedIn">
                {lead.contact?.linkedin_url ? (
                  <a
                    href={lead.contact.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#38BDF8] hover:underline truncate inline-block max-w-[220px]"
                  >
                    {lead.contact.linkedin_url.replace(/^https?:\/\//, "")}
                  </a>
                ) : (
                  "—"
                )}
              </KV>
              <KV label="Source">{lead.source ?? "—"}</KV>
            </dl>
          </CardShell>

          <CardShell title="Company">
            <dl className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 text-sm">
              <KV label="Domain">{lead.company?.domain ?? "—"}</KV>
              <KV label="Industry">{lead.company?.industry ?? "—"}</KV>
              <KV label="Country">{lead.company?.country ?? "—"}</KV>
              <KV label="HQ">{lead.company?.hq_city ?? "—"}</KV>
              <KV label="Size">{lead.company?.size_band ?? "—"}</KV>
              <KV label="Revenue">{lead.company?.revenue_band ?? "—"}</KV>
              <KV label="Website">
                {lead.company?.website ? (
                  <a
                    href={lead.company.website}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#38BDF8] hover:underline"
                  >
                    {lead.company.website.replace(/^https?:\/\//, "")}
                  </a>
                ) : (
                  "—"
                )}
              </KV>
              <KV label="LinkedIn">
                {lead.company?.linkedin_url ? (
                  <a
                    href={lead.company.linkedin_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[#38BDF8] hover:underline truncate inline-block max-w-[220px]"
                  >
                    linkedin.com
                  </a>
                ) : (
                  "—"
                )}
              </KV>
            </dl>
          </CardShell>

          <CardShell
            title="Research Intelligence"
            action={
              research?.doc_url && (
                <a
                  href={research.doc_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs font-medium text-[#FF6D5A] hover:underline"
                >
                  Open full doc ↗
                </a>
              )
            }
          >
            {research?.summary ? (
              <div className="space-y-4">
                <p className="text-sm text-[#B0B8C8] leading-relaxed whitespace-pre-wrap">
                  {research.summary}
                </p>
                {research.sections && typeof research.sections === "object" && (
                  <ResearchSections sections={research.sections as Record<string, unknown>} />
                )}
                {research.model && (
                  <p className="text-[11px] text-[#71717A]">
                    Generated by {research.model} · {fmtDate(research.created_at)}
                  </p>
                )}
              </div>
            ) : (
              <EmptyState
                icon={Sparkles}
                title="No research yet"
                description="Your AVM team can generate an AI research brief for this lead from the agent canvas."
              />
            )}
          </CardShell>

          {(lead.tags.length > 0 || lead.status_tags.length > 0) && (
            <CardShell title="Tags">
              <div className="flex flex-wrap gap-2">
                {lead.status_tags.map((t) => (
                  <StatusPill key={`s-${t}`} label={t} color="#8B5CF6" />
                ))}
                {lead.tags.map((t) => (
                  <StatusPill key={`t-${t}`} label={t} color="#38BDF8" />
                ))}
              </div>
            </CardShell>
          )}
        </div>

        <div className="xl:col-span-2 space-y-5">
          <CardShell title="Lead Summary">
            <dl className="space-y-3 text-sm">
              <KV label="Score">
                {lead.score !== null ? <span className="text-white font-medium">{lead.score}/100</span> : "—"}
              </KV>
              <KV label="Deal value">
                {lead.deal_value_zar ? `R ${Number(lead.deal_value_zar).toLocaleString("en-ZA")}` : "—"}
              </KV>
              <KV label="Probability">{lead.deal_probability !== null ? `${lead.deal_probability}%` : "—"}</KV>
              <KV label="Last touch">{fmtDate(lead.last_touch_at)}</KV>
              <KV label="Next action">{lead.next_action ?? "—"}</KV>
              <KV label="Next action at">{fmtDate(lead.next_action_at)}</KV>
            </dl>
          </CardShell>

          <CardShell title="Activity Timeline">
            {activities.length === 0 ? (
              <EmptyState
                icon={Clock}
                title="No activity yet"
                description="Events (sends, opens, calls, stage changes) will appear here as they happen."
              />
            ) : (
              <ol className="space-y-3">
                {activities.map((a) => (
                  <li key={a.id} className="flex gap-3 text-sm">
                    <div className="flex flex-col items-center">
                      <span
                        aria-hidden
                        className="w-2 h-2 rounded-full mt-1.5"
                        style={{ background: activityColor(a.kind) }}
                      />
                      <span className="flex-1 w-px bg-[rgba(255,255,255,0.06)] mt-1" />
                    </div>
                    <div className="flex-1 pb-2">
                      <div className="text-white text-[13px] font-medium">{activityLabel(a.kind)}</div>
                      <div className="text-[11px] text-[#71717A]">{fmtDate(a.created_at)}</div>
                      {a.kind === "stage_changed" && Boolean(a.meta?.from) && Boolean(a.meta?.to) && (
                        <div className="text-xs text-[#B0B8C8] mt-0.5">
                          {String(a.meta.from)} → {String(a.meta.to)}
                        </div>
                      )}
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </CardShell>

          <CardShell title="Research Report">
            {research ? (
              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-[#B0B8C8]">
                  <FileText size={14} />
                  <span>v{research.id ? 1 : 0} · {fmtDate(research.created_at)}</span>
                </div>
                <div className="flex gap-2">
                  {research.doc_url && (
                    <a
                      href={research.doc_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[#FF6D5A] hover:underline"
                    >
                      Open doc
                    </a>
                  )}
                  {research.pdf_url && (
                    <a
                      href={research.pdf_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[#FF6D5A] hover:underline"
                    >
                      Download PDF
                    </a>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-[#71717A]">No report generated yet.</p>
            )}
          </CardShell>

          <CardShell title="Quick Actions">
            <div className="flex flex-col gap-2 text-sm">
              <Link
                href={composeHref}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.04)] text-white"
              >
                <Mail size={14} className="text-[#FF6D5A]" /> Compose email
              </Link>
              {lead.contact?.phone && (
                <a
                  href={`tel:${lead.contact.phone}`}
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.04)] text-white"
                >
                  <Phone size={14} className="text-[#2DD4BF]" /> Call
                </a>
              )}
              {lead.company?.website && (
                <a
                  href={lead.company.website}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-[rgba(255,255,255,0.08)] hover:bg-[rgba(255,255,255,0.04)] text-white"
                >
                  <Building2 size={14} className="text-[#38BDF8]" /> Visit site
                </a>
              )}
            </div>
          </CardShell>
        </div>
      </div>
    </div>
  );
}

function KV({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col">
      <dt className="text-[11px] uppercase tracking-wider text-[#71717A]">{label}</dt>
      <dd className="text-[#E4E4E7] mt-0.5 break-words">{children}</dd>
    </div>
  );
}

function ResearchSections({ sections }: { sections: Record<string, unknown> }) {
  const entries = Object.entries(sections).filter(([, v]) => Array.isArray(v) && (v as unknown[]).length > 0);
  if (entries.length === 0) return null;
  return (
    <div className="space-y-4">
      {entries.map(([key, values]) => (
        <div key={key}>
          <h4 className="text-[11px] uppercase tracking-wider text-[#71717A] mb-1.5">
            {humanize(key)}
          </h4>
          <ul className="space-y-1 text-sm text-[#B0B8C8] list-disc pl-5">
            {(values as unknown[]).map((v, i) => (
              <li key={i}>{String(v)}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function activityColor(kind: string): string {
  switch (kind) {
    case "replied":
    case "meeting_booked":
    case "won":
      return "#10B981";
    case "lost":
      return "#EF4444";
    case "emailed":
    case "opened":
    case "clicked":
      return "#FF6D5A";
    case "researched":
    case "enriched":
      return "#8B5CF6";
    case "stage_changed":
      return "#38BDF8";
    default:
      return "#71717A";
  }
}
