import { redirect } from "next/navigation";
import { Mail } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { EmptyState } from "@/components/crm/EmptyState";
import { EmailComposer } from "@/components/crm/EmailComposer";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import type { CrmEmailTemplate } from "@/lib/crm/types";

interface ComposerLead {
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

export const dynamic = "force-dynamic";

export default async function CommunicationsPage({
  searchParams,
}: {
  searchParams: Promise<{ lead?: string }>;
}) {
  const ctx = await getCrmViewerContext();
  if (!ctx) redirect("/portal/login");
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) redirect("/portal/crm");

  const params = await searchParams;
  const supabase = await createServerSupabaseClient();

  const [{ data: templates }, { data: config }, lead] = await Promise.all([
    supabase
      .from("crm_email_templates")
      .select("id, name, category, subject, body, variables, is_default")
      .eq("client_id", clientId)
      .order("is_default", { ascending: false })
      .order("name"),
    supabase
      .from("crm_config")
      .select("sender_name, sender_email, sender_signature")
      .eq("client_id", clientId)
      .maybeSingle(),
    params.lead
      ? supabase
          .from("crm_leads")
          .select(
            `
              id,
              next_action, tags,
              company:crm_companies ( name, industry, website ),
              contact:crm_contacts ( first_name, last_name, email, title )
            `,
          )
          .eq("id", params.lead)
          .eq("client_id", clientId)
          .maybeSingle()
          .then((r) => r.data)
      : Promise.resolve(null),
  ]);

  if (!templates || templates.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader title="Communications" description="Compose outreach with templates + merge tags." />
        <EmptyState
          icon={Mail}
          title="No templates yet"
          description="Your AVM team will seed templates automatically on first deploy. If this is showing, the migration may not have run."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Communications"
        description="Pick a template, personalize it, and open in your email client."
      />
      <EmailComposer
        templates={templates as unknown as CrmEmailTemplate[]}
        lead={lead as unknown as ComposerLead | null}
        sender={{
          name: config?.sender_name ?? null,
          email: config?.sender_email ?? null,
          signature: config?.sender_signature ?? null,
        }}
      />
    </div>
  );
}
