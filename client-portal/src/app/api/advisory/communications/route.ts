import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { searchParams } = new URL(req.url);
  const clientId = searchParams.get("client_id") ?? "";

  let query = supabase
    .from("fa_communications")
    .select(
      "*, client:fa_clients!fa_communications_client_id_fkey(id, first_name, last_name), adviser:fa_advisers!fa_communications_adviser_id_fkey(id, full_name)"
    )
    .order("created_at", { ascending: false });

  if (session.role === "client") {
    if (!session.faClientId) {
      return NextResponse.json(
        { error: "No advisory client profile linked" },
        { status: 403 }
      );
    }
    query = query.eq("client_id", session.faClientId);
  } else if (session.firmId) {
    query = query.eq("firm_id", session.firmId);
    if (clientId) {
      query = query.eq("client_id", clientId);
    }
  } else {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch communications" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data: data ?? [] });
}
