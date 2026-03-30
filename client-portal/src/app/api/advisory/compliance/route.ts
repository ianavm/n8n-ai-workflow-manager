import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET() {
  const session = await getSession();
  if (
    !session ||
    !["compliance_officer", "owner"].includes(session.role)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!session.firmId) {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();

  try {
    const { data, error } = await supabase.rpc("fa_get_compliance_summary", {
      p_firm_id: session.firmId,
    });

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch compliance summary" },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, data });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
