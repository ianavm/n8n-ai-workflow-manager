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

  const { error } = await supabase.from("stat_events").insert({
    client_id: auth.clientId,
    workflow_id: workflowId,
    event_type: "message_sent",
    metadata: sanitizeMetadata(body?.metadata),
  });

  if (error) return apiError("Failed to log event", 500);

  await supabase.from("activity_log").insert({
    actor_type: "api",
    actor_id: auth.clientId,
    action: "stat_message_sent",
    target_type: "client",
    target_id: auth.clientId,
    ip_address: extractClientIp(request),
  });

  return NextResponse.json({ success: true }, { status: 201 });
}
