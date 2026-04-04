import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

/* ── Zod schema for POST (create mkt_config) ── */
const createConfigSchema = z.object({
  client_id: z.string().uuid(),
  company_name: z.string().max(200).optional(),
  industry: z.string().max(100).optional(),
  target_audience: z.record(z.string(), z.unknown()).optional(),
  brand_voice: z.record(z.string(), z.unknown()).optional(),
  platforms_enabled: z
    .array(
      z.enum(["google_ads", "meta_ads", "tiktok_ads", "linkedin_ads", "blotato"])
    )
    .min(1, "At least one platform must be enabled"),
  ad_platform_config: z.record(z.string(), z.unknown()).optional(),
  n8n_credentials: z.record(z.string(), z.unknown()).optional(),
  blotato_accounts: z.record(z.string(), z.unknown()).optional(),
  budget_monthly_cap: z.number().int().min(0).default(0),
  budget_alert_threshold: z
    .number()
    .min(0)
    .max(1)
    .default(0.8),
  content_config: z
    .object({
      auto_approve: z.boolean().optional(),
      ai_model: z.string().optional(),
      posting_times: z.record(z.string(), z.string()).optional(),
    })
    .optional(),
  lead_pipeline_stages: z.array(z.string()).optional(),
  lead_assignment_mode: z
    .enum(["round_robin", "manual", "auto_score"])
    .default("round_robin"),
  whatsapp_enabled: z.boolean().optional(),
  email_sender_config: z.record(z.string(), z.unknown()).optional(),
  modules_enabled: z.record(z.string(), z.boolean()).optional(),
});

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }

  const supabase = await createServiceRoleClient();
  const url = new URL(req.url);

  /* ── Return clients without mkt_config (for onboarding dropdown) ── */
  if (url.searchParams.has("clients_without_config")) {
    const [allClientsRes, configsRes] = await Promise.all([
      supabase
        .from("clients")
        .select("id, full_name, email")
        .order("full_name"),
      supabase.from("mkt_config").select("client_id"),
    ]);

    if (allClientsRes.error) {
      return NextResponse.json(
        { error: allClientsRes.error.message },
        { status: 500 }
      );
    }

    const configuredIds = new Set(
      (configsRes.data ?? []).map(
        (c: Record<string, unknown>) => c.client_id as string
      )
    );

    const available = (allClientsRes.data ?? []).filter(
      (c: Record<string, unknown>) => !configuredIds.has(c.id as string)
    );

    return NextResponse.json({ data: available });
  }

  /* ── Default: list all configs with client names ── */
  const { data, error } = await supabase
    .from("mkt_config")
    .select("*, clients(full_name, email)")
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = createConfigSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  /* Check for duplicate */
  const { data: existing } = await supabase
    .from("mkt_config")
    .select("id")
    .eq("client_id", parsed.data.client_id)
    .maybeSingle();

  if (existing) {
    return NextResponse.json(
      { error: "Marketing config already exists for this client" },
      { status: 409 }
    );
  }

  /* Build insert payload (only include provided fields) */
  const insertData: Record<string, unknown> = {
    client_id: parsed.data.client_id,
    platforms_enabled: parsed.data.platforms_enabled,
    budget_monthly_cap: parsed.data.budget_monthly_cap,
    budget_alert_threshold: parsed.data.budget_alert_threshold,
    lead_assignment_mode: parsed.data.lead_assignment_mode,
  };

  if (parsed.data.company_name !== undefined) {
    insertData.company_name = parsed.data.company_name;
  }
  if (parsed.data.industry !== undefined) {
    insertData.industry = parsed.data.industry;
  }
  if (parsed.data.target_audience !== undefined) {
    insertData.target_audience = parsed.data.target_audience;
  }
  if (parsed.data.brand_voice !== undefined) {
    insertData.brand_voice = parsed.data.brand_voice;
  }
  if (parsed.data.ad_platform_config !== undefined) {
    insertData.ad_platform_config = parsed.data.ad_platform_config;
  }
  if (parsed.data.n8n_credentials !== undefined) {
    insertData.n8n_credentials = parsed.data.n8n_credentials;
  }
  if (parsed.data.blotato_accounts !== undefined) {
    insertData.blotato_accounts = parsed.data.blotato_accounts;
  }
  if (parsed.data.content_config !== undefined) {
    insertData.content_config = parsed.data.content_config;
  }
  if (parsed.data.lead_pipeline_stages !== undefined) {
    insertData.lead_pipeline_stages = parsed.data.lead_pipeline_stages;
  }
  if (parsed.data.whatsapp_enabled !== undefined) {
    insertData.whatsapp_enabled = parsed.data.whatsapp_enabled;
  }
  if (parsed.data.email_sender_config !== undefined) {
    insertData.email_sender_config = parsed.data.email_sender_config;
  }
  if (parsed.data.modules_enabled !== undefined) {
    insertData.modules_enabled = parsed.data.modules_enabled;
  }

  const { data, error } = await supabase
    .from("mkt_config")
    .insert(insertData)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data }, { status: 201 });
}
