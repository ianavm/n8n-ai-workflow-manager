import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { z } from "zod";

export async function GET(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const status = url.searchParams.get("status");
  const page = parseInt(url.searchParams.get("page") ?? "1", 10);
  const limit = parseInt(url.searchParams.get("limit") ?? "20", 10);
  const offset = (page - 1) * limit;

  let query = supabase
    .from("acct_invoices")
    .select("*, acct_customers(id, legal_name, email)", { count: "exact" })
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (status) {
    query = query.eq("status", status);
  }

  const { data, error, count } = await query;

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({
    data,
    meta: { total: count ?? 0, page, limit },
  });
}

const createInvoiceSchema = z.object({
  customer_id: z.string().uuid(),
  line_items: z.array(z.object({
    item_code: z.string(),
    description: z.string(),
    qty: z.number().positive(),
    unit_price: z.number().int(),
    vat_rate: z.number().default(0.15),
  })),
  due_date: z.string(),
  reference: z.string().optional(),
  notes: z.string().optional(),
});

export async function POST(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Verify admin
  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (!admin) return NextResponse.json({ error: "Admin access required" }, { status: 403 });

  const body = await req.json();
  const parsed = createInvoiceSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid payload", details: parsed.error.flatten() }, { status: 400 });
  }

  const { customer_id, line_items, due_date, reference, notes } = parsed.data;

  // Get client_id from config
  const { data: config } = await supabase
    .from("acct_config")
    .select("client_id, vat_rate")
    .limit(1)
    .maybeSingle();

  if (!config) {
    return NextResponse.json({ error: "Accounting not configured" }, { status: 400 });
  }

  // Generate invoice number
  const { data: invoiceNumber, error: rpcError } = await supabase.rpc(
    "acct_generate_invoice_number",
    { p_client_id: config.client_id }
  );

  if (rpcError) {
    return NextResponse.json({ error: rpcError.message }, { status: 500 });
  }

  // Calculate totals
  const vatRate = Number(config.vat_rate);
  const enrichedItems = line_items.map((item) => {
    const lineTotal = item.qty * item.unit_price;
    return { ...item, line_total: lineTotal };
  });

  const subtotal = enrichedItems.reduce((sum, item) => sum + item.line_total, 0);
  const vatAmount = Math.round(subtotal * vatRate);
  const total = subtotal + vatAmount;

  const { data: invoice, error: insertError } = await supabase
    .from("acct_invoices")
    .insert({
      client_id: config.client_id,
      customer_id,
      invoice_number: invoiceNumber,
      due_date,
      reference,
      notes,
      line_items: enrichedItems,
      subtotal,
      vat_amount: vatAmount,
      total,
      status: "draft",
      source: "portal",
      created_by: user.email,
    })
    .select()
    .single();

  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  // Audit log
  await supabase.from("acct_audit_log").insert({
    client_id: config.client_id,
    event_type: "INVOICE_CREATED",
    entity_type: "invoice",
    entity_id: invoice.id,
    action: "create",
    actor: user.email ?? "portal",
    result: "success",
    metadata: { invoice_number: invoiceNumber, total },
  });

  return NextResponse.json({ data: invoice }, { status: 201 });
}
