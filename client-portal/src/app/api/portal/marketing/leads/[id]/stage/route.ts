import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const stageChangeSchema = z.object({
  stage: z.string().min(1).max(50),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { id } = await params;
  const body = await req.json();
  const parsed = stageChangeSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Fetch current lead to get old stage
  const { data: currentLead, error: fetchError } = await supabase
    .from("mkt_leads")
    .select("id, stage")
    .eq("id", id)
    .eq("client_id", clientId)
    .single();

  if (fetchError || !currentLead) {
    return NextResponse.json({ error: "Lead not found" }, { status: 404 });
  }

  const oldStage = currentLead.stage as string;
  const newStage = parsed.data.stage;

  // Update lead stage
  const { data: updatedLead, error: updateError } = await supabase
    .from("mkt_leads")
    .update({
      stage: newStage,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("client_id", clientId)
    .select()
    .single();

  if (updateError) {
    return NextResponse.json({ error: updateError.message }, { status: 500 });
  }

  // Record the stage change as an activity
  await supabase.from("mkt_lead_activities").insert({
    client_id: clientId,
    lead_id: id,
    activity_type: "stage_change",
    title: `Stage changed to ${newStage}`,
    metadata: { old_stage: oldStage, new_stage: newStage },
    actor: session.email,
  });

  return NextResponse.json({ data: updatedLead });
}
