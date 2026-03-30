import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const updateMeetingSchema = z.object({
  status: z
    .enum(["scheduled", "confirmed", "in_progress", "completed", "cancelled"])
    .optional(),
  notes: z.string().optional(),
  outcome_summary: z.string().optional(),
  follow_up_required: z.boolean().optional(),
  recording_url: z.string().url().optional(),
});

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function GET(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("fa_meetings")
    .select(
      "*, client:fa_clients!fa_meetings_client_id_fkey(id, first_name, last_name, email), adviser:fa_advisers!fa_meetings_adviser_id_fkey(id, full_name), insights:fa_meeting_insights(*)"
    )
    .eq("id", id)
    .single();

  if (error || !data) {
    return NextResponse.json({ error: "Meeting not found" }, { status: 404 });
  }

  // Access control
  if (session.role === "client") {
    if (session.faClientId !== data.client_id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
    // Strip compliance flags from insights for clients
    const sanitizedInsights = (data.insights ?? []).map(
      ({ compliance_flags: _cf, ...rest }: Record<string, unknown>) => rest
    );
    return NextResponse.json({
      success: true,
      data: { ...data, insights: sanitizedInsights },
    });
  }

  if (
    ["adviser", "compliance_officer"].includes(session.role) &&
    data.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return NextResponse.json({ success: true, data });
}

export async function PATCH(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "owner"].includes(session.role)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const body = await req.json();
  const parsed = updateMeetingSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify meeting belongs to firm
  const { data: existing, error: fetchError } = await supabase
    .from("fa_meetings")
    .select("id, firm_id")
    .eq("id", id)
    .single();

  if (fetchError || !existing) {
    return NextResponse.json({ error: "Meeting not found" }, { status: 404 });
  }

  if (existing.firm_id !== session.firmId) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { data, error } = await supabase
    .from("fa_meetings")
    .update({
      ...parsed.data,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to update meeting" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: session.firmId,
    actor_id: session.profileId,
    actor_type: session.role,
    action: "meeting_updated",
    entity_type: "fa_meetings",
    entity_id: id,
    details: { updated_fields: Object.keys(parsed.data) },
  });

  return NextResponse.json({ success: true, data });
}
