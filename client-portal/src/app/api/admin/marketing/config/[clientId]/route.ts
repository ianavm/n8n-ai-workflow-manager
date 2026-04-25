import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

/* ── Zod schema for PATCH (all fields optional) ── */
const updateConfigSchema = z.object({
  company_name: z.string().max(200).optional(),
  industry: z.string().max(100).optional(),
  target_audience: z.record(z.string(), z.unknown()).optional(),
  brand_voice: z.record(z.string(), z.unknown()).optional(),
  platforms_enabled: z
    .array(
      z.enum(["google_ads", "meta_ads", "tiktok_ads", "linkedin_ads", "blotato"])
    )
    .min(1)
    .optional(),
  ad_platform_config: z.record(z.string(), z.unknown()).optional(),
  n8n_credentials: z.record(z.string(), z.unknown()).optional(),
  blotato_accounts: z.record(z.string(), z.unknown()).optional(),
  budget_monthly_cap: z.number().int().min(0).optional(),
  budget_alert_threshold: z.number().min(0).max(1).optional(),
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
    .optional(),
  whatsapp_enabled: z.boolean().optional(),
  email_sender_config: z.record(z.string(), z.unknown()).optional(),
  workflow_ids: z.record(z.string(), z.unknown()).optional(),
  modules_enabled: z.record(z.string(), z.boolean()).optional(),
});

interface RouteContext {
  params: Promise<{ clientId: string }>;
}

export async function GET(
  _req: NextRequest,
  context: RouteContext
) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }
  if (session.role === "superior_admin") {
    return NextResponse.json(
      { error: "POPIA: superior admin cannot view client business data" },
      { status: 403 }
    );
  }

  const { clientId } = await context.params;
  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("mkt_config")
    .select("*, clients(full_name, email)")
    .eq("client_id", clientId)
    .maybeSingle();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  if (!data) {
    return NextResponse.json(
      { error: "Marketing config not found for this client" },
      { status: 404 }
    );
  }

  /* Flatten client name for convenience */
  const clientRef = data.clients as { full_name: string; email: string } | null;
  const result = {
    ...data,
    client_name: clientRef?.full_name ?? null,
    client_email: clientRef?.email ?? null,
  };

  return NextResponse.json({ data: result });
}

export async function PATCH(
  req: NextRequest,
  context: RouteContext
) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }
  if (session.role === "superior_admin") {
    return NextResponse.json(
      { error: "POPIA: superior admin cannot view client business data" },
      { status: 403 }
    );
  }

  const { clientId } = await context.params;
  const body = await req.json();
  const parsed = updateConfigSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  /* Filter out undefined keys to avoid overwriting with null */
  const updates: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(parsed.data)) {
    if (value !== undefined) {
      updates[key] = value;
    }
  }

  if (Object.keys(updates).length === 0) {
    return NextResponse.json(
      { error: "No fields to update" },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("mkt_config")
    .update(updates)
    .eq("client_id", clientId)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data });
}

export async function DELETE(
  _req: NextRequest,
  context: RouteContext
) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }
  if (session.role === "superior_admin") {
    return NextResponse.json(
      { error: "POPIA: superior admin cannot view client business data" },
      { status: 403 }
    );
  }

  const { clientId } = await context.params;
  const supabase = await createServiceRoleClient();

  const { error } = await supabase
    .from("mkt_config")
    .delete()
    .eq("client_id", clientId);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
