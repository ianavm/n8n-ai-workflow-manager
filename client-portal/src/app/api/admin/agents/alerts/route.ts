import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

async function checkAdminOrApiKey(req: NextRequest): Promise<{ authorized: boolean; reason?: string }> {
  const session = await getSession();
  if (session && (session.role === "superior_admin" || session.role === "staff_admin")) return { authorized: true };
  if (!process.env.INTERNAL_API_KEY) return { authorized: false, reason: "API key not configured" };
  const apiKey = req.headers.get("x-api-key");
  if (apiKey && apiKey === process.env.INTERNAL_API_KEY) return { authorized: true };
  return { authorized: false };
}

export async function GET(req: NextRequest) {
  const auth = await checkAdminOrApiKey(req);
  if (!auth.authorized) {
    return NextResponse.json({ error: auth.reason || "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { data, error } = await supabase
    .from("orchestrator_alerts")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    console.error("[admin/agents/alerts] GET error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  const auth = await checkAdminOrApiKey(req);
  if (!auth.authorized) {
    return NextResponse.json({ error: auth.reason || "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const body = await req.json();

  const { data, error } = await supabase
    .from("orchestrator_alerts")
    .insert({
      agent_id: body.agent_id,
      severity: body.severity || "P3",
      category: body.category || "general",
      title: body.title,
      description: body.description,
      recommended_action: body.recommended_action,
      status: "open",
    })
    .select()
    .single();

  if (error) {
    console.error("[admin/agents/alerts] POST error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
