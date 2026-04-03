import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { z } from "zod";

const approvalSchema = z.object({
  action: z.enum(["approve", "reject"]),
  reason: z.string().optional(),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: admin } = await supabase
    .from("admin_users")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  if (!admin) return NextResponse.json({ error: "Admin access required" }, { status: 403 });

  const body = await req.json();
  const parsed = approvalSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Invalid payload" }, { status: 400 });
  }

  const { action, reason } = parsed.data;

  // Get task
  const { data: task } = await supabase
    .from("acct_tasks")
    .select("*")
    .eq("id", id)
    .single();

  if (!task) return NextResponse.json({ error: "Task not found" }, { status: 404 });
  if (task.status !== "open" && task.status !== "in_progress") {
    return NextResponse.json({ error: "Task already resolved" }, { status: 400 });
  }

  // Update task
  await supabase.from("acct_tasks").update({
    status: "completed",
    approval_action: action === "approve" ? "approved" : "rejected",
    approval_reason: reason,
    resolved_by: user.email,
    completed_at: new Date().toISOString(),
  }).eq("id", id);

  // Update related entity
  if (task.related_entity_type && task.related_entity_id) {
    const table = task.related_entity_type === "invoice"
      ? "acct_invoices"
      : task.related_entity_type === "bill"
      ? "acct_supplier_bills"
      : null;

    if (table && action === "approve") {
      const newStatus = task.related_entity_type === "invoice" ? "approved" : "approved";
      await supabase.from(table).update({ status: newStatus }).eq("id", task.related_entity_id);
    } else if (table && action === "reject") {
      const newStatus = task.related_entity_type === "bill" ? "rejected" : "cancelled";
      await supabase.from(table).update({
        status: newStatus,
        ...(task.related_entity_type === "bill" ? { rejection_reason: reason } : {}),
      }).eq("id", task.related_entity_id);
    }
  }

  // Audit log
  await supabase.from("acct_audit_log").insert({
    client_id: task.client_id,
    event_type: action === "approve" ? "TASK_COMPLETED" : "TASK_COMPLETED",
    entity_type: "task",
    entity_id: id,
    action: `${action}_${task.type}`,
    actor: user.email ?? "admin",
    result: "success",
    metadata: { related_entity_type: task.related_entity_type, related_entity_id: task.related_entity_id, reason },
  });

  return NextResponse.json({ success: true });
}
