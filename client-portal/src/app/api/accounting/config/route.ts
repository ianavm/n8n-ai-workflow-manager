import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

/**
 * GET /api/accounting/config
 * Returns accounting config for the current user.
 * Admin: returns config for ?client_id= param, or first config.
 * Client: returns their own config.
 */
export async function GET(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const requestedClientId = url.searchParams.get("client_id");

  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  let clientId: string | null = null;

  if (admin) {
    if (requestedClientId) {
      clientId = requestedClientId;
    } else {
      // Default to first configured client
      const { data: first } = await supabase
        .from("acct_config")
        .select("client_id")
        .order("created_at", { ascending: true })
        .limit(1)
        .maybeSingle();
      clientId = first?.client_id ?? null;
    }
  } else {
    // Portal client sees own
    const { data: client } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle();
    clientId = client?.id ?? null;
  }

  if (!clientId) {
    return NextResponse.json({ data: null });
  }

  const { data, error } = await supabase
    .from("acct_config")
    .select("*")
    .eq("client_id", clientId)
    .maybeSingle();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Also return list of all configured clients (admin only, for selector)
  let clients: { client_id: string; company_legal_name: string | null }[] = [];
  if (admin) {
    const { data: allConfigs } = await supabase
      .from("acct_config")
      .select("client_id, company_legal_name, company_trading_name")
      .order("created_at", { ascending: true });
    clients = (allConfigs ?? []).map((c) => ({
      client_id: c.client_id,
      company_legal_name: c.company_trading_name || c.company_legal_name || c.client_id,
    }));
  }

  return NextResponse.json({ data, clients, active_client_id: clientId });
}

/**
 * POST /api/accounting/config
 * Create accounting config for a new client (onboarding).
 * Admin only.
 */
const createConfigSchema = z.object({
  client_id: z.string().uuid(),
  company_legal_name: z.string().optional(),
  company_trading_name: z.string().optional(),
  company_vat_number: z.string().optional(),
  default_currency: z.string().default("ZAR"),
  vat_rate: z.number().default(0.15),
  invoice_prefix: z.string().default("INV"),
  default_payment_terms: z.string().default("30 days"),
  accounting_software: z.string().default("none"),
  payment_gateway: z.string().default("none"),
});

export async function POST(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  if (!admin) return NextResponse.json({ error: "Admin access required" }, { status: 403 });

  const body = await req.json();
  const parsed = createConfigSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid payload", details: parsed.error.flatten() }, { status: 400 });
  }

  // Check if config already exists
  const { data: existing } = await supabase
    .from("acct_config")
    .select("id")
    .eq("client_id", parsed.data.client_id)
    .maybeSingle();

  if (existing) {
    return NextResponse.json({ error: "Config already exists for this client" }, { status: 409 });
  }

  // Verify client exists
  const { data: client } = await supabase
    .from("clients")
    .select("id, company_name")
    .eq("id", parsed.data.client_id)
    .maybeSingle();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Use service role for insert (bypasses RLS)
  const serviceClient = await createServiceRoleClient();
  const { data: config, error } = await serviceClient
    .from("acct_config")
    .insert({
      ...parsed.data,
      company_legal_name: parsed.data.company_legal_name || client.company_name,
    })
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ data: config }, { status: 201 });
}

/**
 * PUT /api/accounting/config
 * Update accounting config. Admin only.
 */
export async function PUT(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  if (!admin) return NextResponse.json({ error: "Admin access required" }, { status: 403 });

  const body = await req.json();
  const { id, ...updates } = body;

  if (!id) return NextResponse.json({ error: "Config id required" }, { status: 400 });

  const { data, error } = await supabase
    .from("acct_config")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ data });
}
