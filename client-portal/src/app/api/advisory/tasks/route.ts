import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const createTaskSchema = z.object({
  client_id: z.string().uuid("Valid client ID is required"),
  title: z.string().min(1, "Title is required"),
  description: z.string().optional(),
  type: z
    .enum([
      "document_request",
      "follow_up",
      "compliance",
      "review",
      "general",
    ])
    .default("general"),
  priority: z.enum(["low", "medium", "high", "urgent"]).default("medium"),
  due_date: z.string().optional(),
  assigned_to: z.string().uuid().optional(),
});

const updateTaskSchema = z.object({
  status: z
    .enum(["pending", "in_progress", "completed", "cancelled"])
    .optional(),
  completed_at: z.string().optional(),
  notes: z.string().optional(),
});

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { searchParams } = new URL(req.url);
  const status = searchParams.get("status") ?? "";
  const priority = searchParams.get("priority") ?? "";
  const assignedTo = searchParams.get("assigned_to") ?? "";

  let query = supabase
    .from("fa_tasks")
    .select(
      "*, client:fa_clients!fa_tasks_client_id_fkey(id, first_name, last_name), assignee:fa_advisers!fa_tasks_assigned_to_fkey(id, full_name)"
    )
    .order("due_date", { ascending: true });

  if (session.role === "client") {
    if (!session.faClientId) {
      return NextResponse.json(
        { error: "No advisory client profile linked" },
        { status: 403 }
      );
    }
    query = query.eq("client_id", session.faClientId);
  } else if (session.firmId) {
    query = query.eq("firm_id", session.firmId);
  } else {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  if (status) {
    query = query.eq("status", status);
  }
  if (priority) {
    query = query.eq("priority", priority);
  }
  if (assignedTo) {
    query = query.eq("assigned_to", assignedTo);
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch tasks" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data: data ?? [] });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "staff_admin"].includes(session.role)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!session.firmId) {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const body = await req.json();
  const parsed = createTaskSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify client belongs to firm
  const { data: client, error: clientError } = await supabase
    .from("fa_clients")
    .select("id")
    .eq("id", parsed.data.client_id)
    .eq("firm_id", session.firmId)
    .single();

  if (clientError || !client) {
    return NextResponse.json(
      { error: "Client not found in your firm" },
      { status: 404 }
    );
  }

  const { data, error } = await supabase
    .from("fa_tasks")
    .insert({
      ...parsed.data,
      firm_id: session.firmId,
      status: "pending",
      created_by: session.profileId,
      assigned_to:
        parsed.data.assigned_to ?? session.adviserId ?? session.profileId,
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to create task" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: session.firmId,
    performed_by: session.profileId,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "created",
    entity_type: "fa_tasks",
    entity_id: data.id,
    new_value: { title: parsed.data.title, client_id: parsed.data.client_id },
  });

  return NextResponse.json({ success: true, data }, { status: 201 });
}

export async function PATCH(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { task_id, ...updates } = body;

  if (!task_id) {
    return NextResponse.json(
      { error: "task_id is required" },
      { status: 400 }
    );
  }

  const parsed = updateTaskSchema.safeParse(updates);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify task exists and check access
  const { data: existing, error: fetchError } = await supabase
    .from("fa_tasks")
    .select("id, firm_id, client_id")
    .eq("id", task_id)
    .single();

  if (fetchError || !existing) {
    return NextResponse.json({ error: "Task not found" }, { status: 404 });
  }

  // Clients can only update tasks assigned to them
  if (session.role === "client" && session.faClientId !== existing.client_id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Advisers can only update tasks in their firm
  if (
    ["adviser", "compliance_officer"].includes(session.role) &&
    existing.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const updateData: Record<string, unknown> = {
    ...parsed.data,
    updated_at: new Date().toISOString(),
  };

  // Auto-set completed_at when status changes to completed
  if (parsed.data.status === "completed" && !parsed.data.completed_at) {
    updateData.completed_at = new Date().toISOString();
  }

  const { data, error } = await supabase
    .from("fa_tasks")
    .update(updateData)
    .eq("id", task_id)
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to update task" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: existing.firm_id,
    performed_by: session.profileId,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "updated",
    entity_type: "fa_tasks",
    entity_id: task_id,
    new_value: { updated_fields: Object.keys(parsed.data) },
  });

  return NextResponse.json({ success: true, data });
}
