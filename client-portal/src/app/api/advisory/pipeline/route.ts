import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const updatePipelineSchema = z.object({
  client_id: z.string().uuid("Valid client ID is required"),
  pipeline_stage: z.enum([
    "lead",
    "contacted",
    "intake_complete",
    "discovery_scheduled",
    "discovery_complete",
    "analysis",
    "presentation_scheduled",
    "presentation_complete",
    "implementation",
    "active",
    "inactive",
  ]),
  notes: z.string().optional(),
});

export async function GET() {
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

  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase.rpc("fa_get_pipeline_summary", {
    p_firm_id: session.firmId,
  });

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch pipeline summary" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data });
}

export async function PATCH(req: NextRequest) {
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
  const parsed = updatePipelineSchema.safeParse(body);

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
    .select("id, pipeline_stage")
    .eq("id", parsed.data.client_id)
    .eq("firm_id", session.firmId)
    .single();

  if (clientError || !client) {
    return NextResponse.json(
      { error: "Client not found in your firm" },
      { status: 404 }
    );
  }

  const previousStage = client.pipeline_stage;

  const { data, error } = await supabase
    .from("fa_clients")
    .update({
      pipeline_stage: parsed.data.pipeline_stage,
      pipeline_stage_changed_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("id", parsed.data.client_id)
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to update pipeline stage" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: session.firmId,
    performed_by: session.profileId,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "updated",
    entity_type: "fa_clients",
    entity_id: parsed.data.client_id,
    old_value: { pipeline_stage: previousStage },
    new_value: {
      pipeline_stage: parsed.data.pipeline_stage,
      notes: parsed.data.notes ?? null,
    },
  });

  return NextResponse.json({ success: true, data });
}
