import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const supabase = await createServiceRoleClient();
  const url = new URL(req.url);

  const channel = url.searchParams.get("channel");
  const status = url.searchParams.get("status");
  const page = Math.max(1, parseInt(url.searchParams.get("page") ?? "1", 10));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") ?? "20", 10)));
  const offset = (page - 1) * limit;

  let query = supabase
    .from("mkt_conversations")
    .select(
      "*, lead:mkt_leads!lead_id(first_name, last_name, email)",
      { count: "exact" }
    )
    .eq("client_id", clientId)
    .order("last_message_at", { ascending: false, nullsFirst: false })
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (channel) {
    query = query.eq("channel", channel);
  }
  if (status) {
    query = query.eq("status", status);
  }

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    data,
    meta: { total: count ?? 0, page, limit },
  });
}
