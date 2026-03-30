import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("fa_pricing")
    .select(
      "*, client:fa_clients!fa_pricing_client_id_fkey(id, first_name, last_name, email), adviser:fa_advisers!fa_pricing_adviser_id_fkey(id, full_name)"
    )
    .eq("id", id)
    .single();

  if (error || !data) {
    return NextResponse.json(
      { error: "Pricing record not found" },
      { status: 404 }
    );
  }

  // Access control
  if (session.role === "client") {
    if (session.faClientId !== data.client_id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  } else if (
    ["adviser", "compliance_officer"].includes(session.role) &&
    data.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return NextResponse.json({ success: true, data });
}
