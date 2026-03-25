import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET() {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const serviceClient = await createServiceRoleClient();

  // Get client record
  const { data: client } = await serviceClient
    .from("clients")
    .select("id")
    .eq("id", session.profileId)
    .single();

  if (!client) return NextResponse.json([]);

  // Get tickets for this client
  const { data, error } = await serviceClient
    .from("support_tickets")
    .select("*")
    .eq("client_id", client.id)
    .order("created_at", { ascending: false });

  if (error) {
    if (error.code === "42P01") return NextResponse.json([]);
    console.error("[portal/support] GET error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  return NextResponse.json(data || []);
}

export async function POST(req: Request) {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const serviceClient = await createServiceRoleClient();
  const body = await req.json();

  // Validate input
  if (!body.subject || typeof body.subject !== "string" || body.subject.trim().length === 0) {
    return NextResponse.json({ error: "Subject is required and must be a string" }, { status: 400 });
  }
  if (body.subject.length > 200) {
    return NextResponse.json({ error: "Subject must be 200 characters or fewer" }, { status: 400 });
  }
  if (!body.body || typeof body.body !== "string" || body.body.trim().length === 0) {
    return NextResponse.json({ error: "Body is required and must be a string" }, { status: 400 });
  }
  if (body.body.length > 10000) {
    return NextResponse.json({ error: "Body must be 10,000 characters or fewer" }, { status: 400 });
  }

  // Get client record
  const { data: client } = await serviceClient
    .from("clients")
    .select("id, email")
    .eq("id", session.profileId)
    .single();

  if (!client) return NextResponse.json({ error: "Client not found" }, { status: 404 });

  const ticketId = `TKT-${Date.now().toString(36).toUpperCase()}`;

  const { data, error } = await serviceClient
    .from("support_tickets")
    .insert({
      ticket_id: ticketId,
      client_id: client.id,
      client_email: client.email,
      subject: body.subject,
      body: body.body,
      priority: "P3",
      status: "Open",
      created_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (error) {
    // If table doesn't exist, create a minimal response
    if (error.code === "42P01") {
      // Still forward to self-healing webhook
      forwardToSelfHealing(ticketId, body, client.email).catch(() => {});
      return NextResponse.json({
        ticket_id: ticketId,
        status: "Open",
        message: "Ticket created (support system initializing)",
      }, { status: 201 });
    }
    console.error("[portal/support] POST error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }

  // Forward to self-healing webhook for triage + email alert
  forwardToSelfHealing(ticketId, body, client.email).catch(() => {});

  return NextResponse.json(data, { status: 201 });
}

async function forwardToSelfHealing(
  ticketId: string,
  body: { subject?: string; body?: string },
  clientEmail: string
) {
  const webhookUrl = process.env.N8N_SELFHEALING_WEBHOOK_URL
    || "https://ianimmelman89.app.n8n.cloud/webhook/self-healing/report";

  await fetch(webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      error_message: `[${ticketId}] ${body.subject || "No subject"}: ${body.body || "No details"}`,
      workflow_name: "Client Portal Support",
      error_node: "Client Report",
      execution_id: ticketId,
      source: "portal",
      reporter_email: clientEmail,
    }),
  });
}
