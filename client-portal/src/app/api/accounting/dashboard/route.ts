import { NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Check if admin
  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  // Get client_id (admin sees first client, portal user sees own)
  let clientId: string | null = null;

  if (admin) {
    const { data: firstClient } = await supabase
      .from("acct_config")
      .select("client_id")
      .limit(1)
      .maybeSingle();
    clientId = firstClient?.client_id ?? null;
  } else {
    const { data: client } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle();
    clientId = client?.id ?? null;
  }

  if (!clientId) {
    return NextResponse.json({
      data: {
        total_receivables: 0, total_payables: 0, overdue_amount: 0,
        overdue_invoices: 0, cash_received_month: 0, pending_approvals: 0,
        reconciliation_pending: 0, workflow_failures: 0, invoices_sent_today: 0,
        cash_received_today: 0, bills_awaiting_approval: 0, bills_due_this_week: 0,
      },
    });
  }

  const { data, error } = await supabase.rpc("acct_get_dashboard_kpis", {
    p_client_id: clientId,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data });
}
