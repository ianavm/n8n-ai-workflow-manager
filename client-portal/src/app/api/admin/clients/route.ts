import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { validatePassword, isValidClientStatus } from "@/lib/validation";

// GET /api/admin/clients — list all clients (admin only)
export async function GET() {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();

  const { data: clients, error } = await supabase
    .from("clients")
    .select("*")
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: "Failed to fetch clients" }, { status: 500 });
  }

  // Batch fetch stats and workflows for all clients (avoids N+1)
  const clientIds = (clients || []).map((c) => c.id);

  const [{ data: allStats }, { data: allWorkflows }] = await Promise.all([
    supabase
      .from("stat_events")
      .select("client_id, event_type")
      .in("client_id", clientIds),
    supabase
      .from("workflows")
      .select("client_id")
      .in("client_id", clientIds)
      .eq("status", "active"),
  ]);

  // Build lookup maps
  const statsMap = new Map<string, Record<string, number>>();
  for (const s of allStats || []) {
    const counts = statsMap.get(s.client_id) || {};
    counts[s.event_type] = (counts[s.event_type] || 0) + 1;
    statsMap.set(s.client_id, counts);
  }

  const workflowMap = new Map<string, number>();
  for (const w of allWorkflows || []) {
    workflowMap.set(w.client_id, (workflowMap.get(w.client_id) || 0) + 1);
  }

  const enriched = (clients || []).map((client) => {
    const eventCounts = statsMap.get(client.id) || {};
    return {
      ...client,
      active_workflows: workflowMap.get(client.id) || 0,
      messages_sent: eventCounts.message_sent || 0,
      messages_received: eventCounts.message_received || 0,
      leads_created: eventCounts.lead_created || 0,
      total_crashes: eventCounts.workflow_crash || 0,
    };
  });

  return NextResponse.json(enriched);
}

// POST /api/admin/clients — create a new client
export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { email, full_name, company_name, password } = body;

  if (!email || !full_name || !password) {
    return NextResponse.json(
      { error: "email, full_name, and password are required" },
      { status: 400 }
    );
  }

  // Validate password strength
  const passwordError = validatePassword(password);
  if (passwordError) {
    return NextResponse.json({ error: passwordError }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  // Create auth user
  const { data: authUser, error: authError } =
    await supabase.auth.admin.createUser({
      email,
      password,
      email_confirm: true,
    });

  if (authError) {
    return NextResponse.json(
      { error: "Failed to create user" },
      { status: 400 }
    );
  }

  // Create client record
  const { data: client, error: clientError } = await supabase
    .from("clients")
    .insert({
      auth_user_id: authUser.user.id,
      email,
      full_name,
      company_name: company_name || null,
      created_by: session.profileId,
    })
    .select()
    .single();

  if (clientError) {
    // Rollback: delete auth user
    await supabase.auth.admin.deleteUser(authUser.user.id);
    return NextResponse.json(
      { error: "Failed to create client record" },
      { status: 500 }
    );
  }

  // Log activity
  await supabase.from("activity_log").insert({
    actor_type: "admin",
    actor_id: session.profileId,
    action: "client_created",
    target_type: "client",
    target_id: client.id,
    details: { email, full_name },
  });

  return NextResponse.json(client, { status: 201 });
}

// PATCH /api/admin/clients — update client status
export async function PATCH(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { client_id, status: newStatus } = body;

  if (!client_id || !newStatus) {
    return NextResponse.json(
      { error: "client_id and status are required" },
      { status: 400 }
    );
  }

  // Validate status is an allowed value
  if (!isValidClientStatus(newStatus)) {
    return NextResponse.json(
      { error: "status must be one of: active, suspended, inactive" },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  const { error } = await supabase
    .from("clients")
    .update({ status: newStatus, updated_at: new Date().toISOString() })
    .eq("id", client_id);

  if (error) {
    return NextResponse.json({ error: "Failed to update client" }, { status: 500 });
  }

  await supabase.from("activity_log").insert({
    actor_type: "admin",
    actor_id: session.profileId,
    action: `client_status_${newStatus}`,
    target_type: "client",
    target_id: client_id,
  });

  return NextResponse.json({ success: true });
}
