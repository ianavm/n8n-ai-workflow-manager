import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

// Note: Support tickets are stored in Airtable (Support base).
// This endpoint serves as a proxy/cache. For now, it returns
// tickets from a Supabase shadow table if one exists, or an empty array.
// In production, n8n workflows will sync Airtable tickets to Supabase
// for faster portal queries.

export async function GET() {
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
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data || []);
}

export async function POST(req: Request) {
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
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data, { status: 201 });
}
