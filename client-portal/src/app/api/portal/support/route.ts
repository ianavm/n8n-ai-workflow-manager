import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";
import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

const serviceClient = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

async function getAuthUser() {
  const cookieStore = await cookies();
  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    { cookies: { getAll: () => cookieStore.getAll() } }
  );
  const { data: { user } } = await supabase.auth.getUser();
  return user;
}

export async function GET() {
  const user = await getAuthUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Get client record
  const { data: client } = await serviceClient
    .from("clients")
    .select("id")
    .eq("auth_user_id", user.id)
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
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data || []);
}

export async function POST(req: Request) {
  const user = await getAuthUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const body = await req.json();

  // Get client record
  const { data: client } = await serviceClient
    .from("clients")
    .select("id, email")
    .eq("auth_user_id", user.id)
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
    return NextResponse.json({ error: error.message }, { status: 500 });
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
