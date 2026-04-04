import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface RouteContext {
  params: Promise<{ clientId: string }>;
}

export async function GET(_req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }

  const { clientId } = await context.params;

  if (!clientId || typeof clientId !== "string" || clientId.length < 10) {
    return NextResponse.json({ error: "Invalid client ID" }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  const [rpcRes, interventionsRes, clientRes] = await Promise.all([
    supabase.rpc("get_client_health_details", { p_client_id: clientId }),
    supabase
      .from("health_interventions")
      .select("*")
      .eq("client_id", clientId)
      .order("created_at", { ascending: false })
      .limit(20),
    supabase
      .from("clients")
      .select("id, full_name, company_name, email")
      .eq("id", clientId)
      .maybeSingle(),
  ]);

  if (rpcRes.error && rpcRes.error.code !== "42883") {
    return NextResponse.json(
      { error: "Failed to load health data" },
      { status: 500 }
    );
  }

  return NextResponse.json({
    health: rpcRes.data ?? null,
    interventions: interventionsRes.data ?? [],
    client: clientRes.data ?? null,
  });
}
