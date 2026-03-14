import { NextRequest, NextResponse } from "next/server";
import { validateApiKey, apiError } from "@/lib/api-keys";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { isValidUUID, sanitizeMetadata, extractClientIp } from "@/lib/validation";

export async function POST(request: NextRequest) {
  const auth = await validateApiKey(request);
  if (!auth.ok) return apiError(auth.error, auth.status);

  const body = await request.json().catch(() => null);
  const supabase = await createServiceRoleClient();

  const workflowId = isValidUUID(body?.workflow_id) ? body.workflow_id : null;
  const metadata = sanitizeMetadata(body?.metadata);
  const errorMessage =
    typeof metadata?.error === "string"
      ? metadata.error.slice(0, 500)
      : "Unknown error";

  // Log the crash event
  const { error } = await supabase.from("stat_events").insert({
    client_id: auth.clientId,
    workflow_id: workflowId,
    event_type: "workflow_crash",
    metadata,
  });

  if (error) return apiError("Failed to log event", 500);

  // Also log as a failed execution if workflow_id provided
  if (workflowId) {
    await supabase.from("workflow_executions").insert({
      client_id: auth.clientId,
      workflow_id: workflowId,
      status: "failure",
      error_message: errorMessage,
    });

    // Update workflow status to 'error' (scoped to client to prevent cross-tenant manipulation)
    await supabase
      .from("workflows")
      .update({ status: "error", updated_at: new Date().toISOString() })
      .eq("id", workflowId)
      .eq("client_id", auth.clientId);
  }

  await supabase.from("activity_log").insert({
    actor_type: "api",
    actor_id: auth.clientId,
    action: "stat_workflow_crash",
    target_type: "client",
    target_id: auth.clientId,
    details: { workflow_id: workflowId, error: errorMessage },
    ip_address: extractClientIp(request),
  });

  return NextResponse.json({ success: true }, { status: 201 });
}
