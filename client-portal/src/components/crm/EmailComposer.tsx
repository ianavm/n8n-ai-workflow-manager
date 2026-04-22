"use client";

import { useMemo, useState } from "react";
import { ExternalLink, Plus, Send } from "lucide-react";
import { CardShell } from "./CardShell";
import { extractMergeTags, renderMergeTags } from "@/lib/crm/merge-tags";
import type { CrmEmailTemplate } from "@/lib/crm/types";

interface LeadShape {
  id: string;
  next_action: string | null;
  tags: string[];
  company: { name: string | null; industry: string | null; website: string | null } | null;
  contact: {
    first_name: string | null;
    last_name: string | null;
    email: string | null;
    title: string | null;
  } | null;
}

interface Props {
  templates: CrmEmailTemplate[];
  lead: LeadShape | null;
  sender: { name: string | null; email: string | null; signature: string | null };
}

type TemplateLite = Pick<CrmEmailTemplate, "id" | "name" | "category" | "subject" | "body" | "variables">;

export function EmailComposer({ templates, lead, sender }: Props) {
  const [templateId, setTemplateId] = useState<string>(templates[0]?.id ?? "");
  const [subject, setSubject] = useState<string>(templates[0]?.subject ?? "");
  const [body, setBody] = useState<string>(templates[0]?.body ?? "");
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [toEmail, setToEmail] = useState<string>(lead?.contact?.email ?? "");

  const mergeCtx = useMemo(
    () => ({
      lead: { id: lead?.id ?? "", next_action: lead?.next_action ?? null, tags: lead?.tags ?? [] },
      contact: lead?.contact ?? null,
      company: lead?.company ?? null,
      sender,
      custom,
    }),
    [lead, sender, custom],
  );

  const renderedSubject = useMemo(() => renderMergeTags(subject, mergeCtx), [subject, mergeCtx]);
  const renderedBody = useMemo(() => renderMergeTags(body, mergeCtx), [body, mergeCtx]);

  const variables = useMemo(() => {
    const set = new Set<string>();
    for (const t of extractMergeTags(subject)) set.add(t);
    for (const t of extractMergeTags(body)) set.add(t);
    return Array.from(set);
  }, [subject, body]);

  // Which variables don't have an automatic resolver (user needs to fill)
  const AUTO_TAGS = new Set([
    "first_name",
    "last_name",
    "contact_name",
    "contact_email",
    "title",
    "company",
    "industry",
    "website",
    "sender_name",
    "sender_email",
    "signature",
  ]);
  const customVars = variables.filter((v) => !AUTO_TAGS.has(v));

  function selectTemplate(id: string) {
    const tpl = templates.find((t) => t.id === id) as TemplateLite | undefined;
    if (!tpl) return;
    setTemplateId(id);
    setSubject(tpl.subject);
    setBody(tpl.body);
  }

  const mailtoHref = buildMailto({
    to: toEmail,
    subject: renderedSubject,
    body: renderedBody,
  });

  const canSend = Boolean(toEmail && renderedSubject && renderedBody);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-5 gap-5">
      <div className="xl:col-span-3 space-y-5">
        <CardShell title="Email Composer">
          <div className="space-y-4">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-[#71717A]">Template</label>
              <select
                value={templateId}
                onChange={(e) => selectTemplate(e.target.value)}
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
              >
                {templates.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-wider text-[#71717A]">To</label>
              <input
                type="email"
                value={toEmail}
                onChange={(e) => setToEmail(e.target.value)}
                placeholder="recipient@example.com"
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white placeholder:text-[#71717A] focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
              />
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-wider text-[#71717A]">Subject</label>
              <input
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
              />
            </div>

            {variables.length > 0 && (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-[#71717A]">Merge tags in use</label>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {variables.map((v) => (
                    <button
                      key={v}
                      type="button"
                      onClick={() => insertAtCursor(`{{${v}}}`, setBody)}
                      className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-mono rounded-md border border-[rgba(255,109,90,0.3)] bg-[rgba(255,109,90,0.08)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.15)]"
                    >
                      <Plus size={10} />
                      {v}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label className="text-[11px] uppercase tracking-wider text-[#71717A]">Body</label>
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                rows={12}
                className="mt-1 w-full px-3 py-2 text-sm rounded-lg bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white placeholder:text-[#71717A] focus:outline-none focus:border-[rgba(255,109,90,0.4)] font-mono resize-y"
              />
            </div>

            {customVars.length > 0 && (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-[#71717A]">
                  Fill custom values
                </label>
                <div className="mt-1 space-y-2">
                  {customVars.map((v) => (
                    <div key={v} className="flex items-center gap-2">
                      <span className="w-32 text-xs font-mono text-[#FF6D5A] truncate">{`{{${v}}}`}</span>
                      <input
                        value={custom[v] ?? ""}
                        onChange={(e) => setCustom((c) => ({ ...c, [v]: e.target.value }))}
                        placeholder={`Value for ${v}`}
                        className="flex-1 px-3 py-1.5 text-sm rounded-md bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white placeholder:text-[#71717A] focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2">
              <a
                href={canSend ? mailtoHref : undefined}
                aria-disabled={!canSend}
                className={`inline-flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg transition-colors ${
                  canSend
                    ? "border border-[rgba(255,109,90,0.3)] bg-[rgba(255,109,90,0.12)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.18)]"
                    : "border border-[rgba(255,255,255,0.06)] text-[#71717A] opacity-50 cursor-not-allowed"
                }`}
              >
                <Send size={14} />
                Open in email client
                <ExternalLink size={12} />
              </a>
              <span className="text-xs text-[#71717A]">Opens your default mail app with fields pre-filled.</span>
            </div>
          </div>
        </CardShell>
      </div>

      <div className="xl:col-span-2">
        <CardShell title="Live Preview">
          <div className="space-y-3">
            <div>
              <div className="text-[11px] uppercase tracking-wider text-[#71717A]">Subject</div>
              <div className="mt-0.5 text-sm font-medium text-white">{renderedSubject || "—"}</div>
            </div>
            <div>
              <div className="text-[11px] uppercase tracking-wider text-[#71717A]">Body</div>
              <pre className="mt-0.5 text-sm text-[#E4E4E7] whitespace-pre-wrap break-words font-sans">
                {renderedBody || "Preview appears as you type."}
              </pre>
            </div>
          </div>
        </CardShell>
      </div>
    </div>
  );
}

function buildMailto({ to, subject, body }: { to: string; subject: string; body: string }): string {
  const params = new URLSearchParams();
  if (subject) params.set("subject", subject);
  if (body) params.set("body", body);
  const q = params.toString();
  return `mailto:${encodeURIComponent(to)}${q ? `?${q}` : ""}`;
}

function insertAtCursor(snippet: string, setter: (updater: (prev: string) => string) => void) {
  setter((prev) => (prev ? `${prev} ${snippet}` : snippet));
}
