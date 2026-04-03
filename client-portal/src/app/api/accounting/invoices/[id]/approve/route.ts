import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function POST(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
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

  // Get current invoice
  const { data: invoice } = await supabase
    .from("acct_invoices")
    .select("id, status, client_id, invoice_number")
    .eq("id", id)
    .single();

  if (!invoice) return NextResponse.json({ error: "Invoice not found" }, { status: 404 });
  if (invoice.status !== "draft") {
    return NextResponse.json({ error: `Cannot approve invoice in '${invoice.status}' status` }, { status: 400 });
  }

  const { data: updated, error } = await supabase
    .from("acct_invoices")
    .update({ status: "approved" })
    .eq("id", id)
    .select()
    .single();

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  // Audit log
  await supabase.from("acct_audit_log").insert({
    client_id: invoice.client_id,
    event_type: "INVOICE_APPROVED",
    entity_type: "invoice",
    entity_id: id,
    action: "approve",
    actor: user.email ?? "admin",
    result: "success",
    metadata: { invoice_number: invoice.invoice_number },
  });

  return NextResponse.json({ data: updated });
}
