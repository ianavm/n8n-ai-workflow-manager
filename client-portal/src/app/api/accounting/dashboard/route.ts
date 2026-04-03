import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

const EMPTY_KPIS = {
  total_receivables: 0, total_payables: 0, overdue_amount: 0,
  overdue_invoices: 0, cash_received_month: 0, pending_approvals: 0,
  reconciliation_pending: 0, workflow_failures: 0, invoices_sent_today: 0,
  cash_received_today: 0, bills_awaiting_approval: 0, bills_due_this_week: 0,
};

export async function GET(req: NextRequest) {
  const supabase = await createServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const url = new URL(req.url);
  const requestedClientId = url.searchParams.get("client_id");

  // Check if admin
  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  let clientId: string | null = null;

  if (admin) {
    if (requestedClientId) {
      // Admin selected specific client
      clientId = requestedClientId;
    } else {
      // Default to first configured client
      const { data: firstClient } = await supabase
        .from("acct_config")
        .select("client_id")
        .order("created_at", { ascending: true })
        .limit(1)
        .maybeSingle();
      clientId = firstClient?.client_id ?? null;
    }
  } else {
    // Portal client sees own data only
    const { data: client } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle();
    clientId = client?.id ?? null;
  }

  if (!clientId) {
    return NextResponse.json({ data: EMPTY_KPIS });
  }

  const { data, error } = await supabase.rpc("acct_get_dashboard_kpis", {
    p_client_id: clientId,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({ data, client_id: clientId });
}
