import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(_req: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (session.role === "superior_admin") {
    return NextResponse.json(
      { error: "POPIA: superior admin cannot view client business data" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();
  const [healthRes, renewalRes, clientsRes] = await Promise.all([
    supabase
      .from("client_health_scores")
      .select("*")
      .order("composite_score", { ascending: true }),
    supabase
      .from("renewal_pipeline")
      .select("*")
      .order("days_until_renewal", { ascending: true }),
    supabase.from("clients").select("id, company_name, email"),
  ]);

  return NextResponse.json({
    healthScores: healthRes.data || [],
    renewals: renewalRes.data || [],
    clients: clientsRes.data || [],
  });
}
