import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import { renderMergeTags } from "@/lib/crm/merge-tags";

const bodySchema = z.object({
  templateId: z.string().uuid(),
  leadId: z.string().uuid(),
  custom: z.record(z.string(), z.string()).optional(),
  client: z.string().uuid().optional(),
});

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid body" }, { status: 400 });
  }
  const { templateId, leadId, custom, client } = parsed.data;

  const ctx = await getCrmViewerContext(client);
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass client" },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();
  const [{ data: template }, { data: lead }, { data: config }] = await Promise.all([
    supabase
      .from("crm_email_templates")
      .select("id, name, subject, body, variables")
      .eq("id", templateId)
      .eq("client_id", clientId)
      .maybeSingle(),
    supabase
      .from("crm_leads")
      .select(
        `
          id, next_action, tags,
          company:crm_companies ( name, industry, website ),
          contact:crm_contacts ( first_name, last_name, email, title )
        `,
      )
      .eq("id", leadId)
      .eq("client_id", clientId)
      .maybeSingle(),
    supabase
      .from("crm_config")
      .select("sender_name, sender_email, sender_signature")
      .eq("client_id", clientId)
      .maybeSingle(),
  ]);

  if (!template) return NextResponse.json({ success: false, error: "Template not found" }, { status: 404 });
  if (!lead) return NextResponse.json({ success: false, error: "Lead not found" }, { status: 404 });

  const mergeCtx = {
    lead: { id: lead.id, next_action: lead.next_action, tags: lead.tags ?? [] },
    contact: (lead as unknown as { contact: Record<string, unknown> | null }).contact as
      | { first_name: string | null; last_name: string | null; email: string | null; title: string | null }
      | null,
    company: (lead as unknown as { company: Record<string, unknown> | null }).company as
      | { name: string | null; industry: string | null; website: string | null }
      | null,
    sender: {
      name: config?.sender_name ?? null,
      email: config?.sender_email ?? null,
      signature: config?.sender_signature ?? null,
    },
    custom,
  };

  return NextResponse.json({
    success: true,
    data: {
      templateId: template.id,
      subject: renderMergeTags(template.subject, mergeCtx),
      body: renderMergeTags(template.body, mergeCtx),
      toEmail: mergeCtx.contact?.email ?? null,
    },
  });
}
