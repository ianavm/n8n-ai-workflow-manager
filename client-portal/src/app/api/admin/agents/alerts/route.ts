import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

async function checkAdminOrApiKey(req: NextRequest): Promise<boolean> {
  const session = await getSession();
  if (session && (session.role === "owner" || session.role === "employee")) return true;
  const apiKey = req.headers.get("x-api-key");
  if (apiKey && apiKey === process.env.INTERNAL_API_KEY) return true;
  return false;
}

export async function GET(req: NextRequest) {
  if (!(await checkAdminOrApiKey(req))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { data, error } = await supabase
    .from("orchestrator_alerts")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  if (!(await checkAdminOrApiKey(req))) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
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
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
