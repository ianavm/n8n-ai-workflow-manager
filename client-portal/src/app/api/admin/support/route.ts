import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

async function checkAdminOrApiKey(req: NextRequest): Promise<{ authorized: boolean; reason?: string }> {
  const session = await getSession();
  if (session && (session.role === "owner" || session.role === "employee")) return { authorized: true };
  if (!process.env.INTERNAL_API_KEY) return { authorized: false, reason: "API key not configured" };
  const apiKey = req.headers.get("x-api-key");
  if (apiKey && apiKey === process.env.INTERNAL_API_KEY) return { authorized: true };
  return { authorized: false };
}

// Note: Support tickets are stored in Airtable (Support base).
// This endpoint serves as a proxy/cache. For now, it returns
// tickets from a Supabase shadow table if one exists, or an empty array.
// In production, n8n workflows will sync Airtable tickets to Supabase
// for faster portal queries.

export async function GET(req: NextRequest) {
  const auth = await checkAdminOrApiKey(req);
  if (!auth.authorized) {
    return NextResponse.json({ error: auth.reason || "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  // Try reading from a support_tickets shadow table
  const { data, error } = await supabase
    .from("support_tickets")
    .select("*")
    .order("created_at", { ascending: false })
    .limit(100);

  if (error) {
    // Table might not exist yet - return empty array
    if (error.code === "42P01") {
      return NextResponse.json([]);
    }
    console.error("[admin/support] GET error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  return NextResponse.json(data || []);
}

export async function POST(req: NextRequest) {
  const auth = await checkAdminOrApiKey(req);
  if (!auth.authorized) {
    return NextResponse.json({ error: auth.reason || "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const body = await req.json();

  // Create or update a support ticket shadow record
  const { data, error } = await supabase
    .from("support_tickets")
    .upsert(
      {
        ticket_id: body.ticket_id,
        client_email: body.client_email,
        subject: body.subject,
        department: body.department,
        priority: body.priority || "P3",
        status: body.status || "Open",
        ai_summary: body.ai_summary,
        ai_suggested_resolution: body.ai_suggested_resolution,
        sla_due_at: body.sla_due_at,
        created_at: body.created_at || new Date().toISOString(),
        resolved_at: body.resolved_at,
      },
      { onConflict: "ticket_id" }
    )
    .select()
    .single();

  if (error) {
    console.error("[admin/support] POST error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
