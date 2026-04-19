import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { incrementUsage } from "@/lib/feature-gate";
import { isValidUUID } from "@/lib/validation";
import { z } from "zod";

const SOURCE_ENUM = z.enum([
  "website",
  "google_ads",
  "meta_ads",
  "tiktok_ads",
  "linkedin_ads",
  "referral",
  "cold_outreach",
  "whatsapp",
  "phone",
  "email",
  "event",
  "partner",
  "organic",
  "other",
]);

const leadCaptureSchema = z.object({
  first_name: z.string().max(100).optional(),
  last_name: z.string().max(100).optional(),
  email: z.string().email().max(255).optional(),
  phone: z.string().max(30).optional(),
  company: z.string().max(200).optional(),
  source: SOURCE_ENUM,
  source_detail: z.string().max(500).optional(),
  campaign_id: z.string().uuid().optional(),
  utm_source: z.string().max(200).optional(),
  utm_medium: z.string().max(200).optional(),
  utm_campaign: z.string().max(200).optional(),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ clientId: string }> }
) {
  const webhookSecret = req.headers.get("x-n8n-webhook-secret");
  // Per-endpoint secret with fallback to the shared one during migration.
  const expectedSecret =
    process.env.N8N_WEBHOOK_SECRET_MKT_LEAD ?? process.env.N8N_WEBHOOK_SECRET;

  if (!expectedSecret || webhookSecret !== expectedSecret) {
    return NextResponse.json({ error: "Invalid webhook secret" }, { status: 401 });
  }

  const { clientId } = await params;
  if (!isValidUUID(clientId)) {
    return NextResponse.json({ error: "Invalid client ID" }, { status: 400 });
  }

  const body = await req.json();
  const parsed = leadCaptureSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Confirm the clientId refers to a real client before accepting writes —
  // prevents orphaned rows from a forged/stale client UUID even with the
  // webhook secret.
  const { data: clientRow } = await supabase
    .from("clients")
    .select("id")
    .eq("id", clientId)
    .maybeSingle();
  if (!clientRow) {
    return NextResponse.json({ error: "Unknown client" }, { status: 404 });
  }

  // Build metadata from UTM params
  const metadata: Record<string, string> = {};
  if (parsed.data.utm_source) metadata.utm_source = parsed.data.utm_source;
  if (parsed.data.utm_medium) metadata.utm_medium = parsed.data.utm_medium;
  if (parsed.data.utm_campaign) metadata.utm_campaign = parsed.data.utm_campaign;

  const { data: lead, error: insertError } = await supabase
    .from("mkt_leads")
    .insert({
      client_id: clientId,
      first_name: parsed.data.first_name,
      last_name: parsed.data.last_name,
      email: parsed.data.email,
      phone: parsed.data.phone,
      company: parsed.data.company,
      source: parsed.data.source,
      source_detail: parsed.data.source_detail,
      campaign_id: parsed.data.campaign_id,
      stage: "new",
      metadata: Object.keys(metadata).length > 0 ? metadata : null,
    })
    .select()
    .single();

  if (insertError) {
    console.error("[webhooks/mkt/lead-capture] Insert failed:", insertError);
    return NextResponse.json(
      { error: "Failed to capture lead" },
      { status: 500 }
    );
  }

  // Record initial activity
  await supabase.from("mkt_lead_activities").insert({
    client_id: clientId,
    lead_id: lead.id,
    activity_type: "system",
    title: `Lead captured via ${parsed.data.source}`,
    actor: "n8n",
    metadata: Object.keys(metadata).length > 0 ? metadata : null,
  });

  // Increment lead count for feature gating
  await incrementUsage(clientId, "leads");

  return NextResponse.json({ success: true, lead_id: lead.id }, { status: 201 });
}
