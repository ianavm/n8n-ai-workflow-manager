import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const clientId =
    session.role === "client" ? session.profileId : null;

  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { data, error } = await supabase.rpc("mkt_get_dashboard_kpis", {
    p_client_id: clientId,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
