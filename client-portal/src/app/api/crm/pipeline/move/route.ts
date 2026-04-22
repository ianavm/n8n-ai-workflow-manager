import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

const bodySchema = z.object({
  leadId: z.string().uuid(),
  toStage: z.string().trim().min(1).max(64),
  client: z.string().uuid().optional(),
});

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid body" }, { status: 400 });
  }

  const { leadId, toStage, client } = parsed.data;
  const ctx = await getCrmViewerContext(client);
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass client" },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();

  // Validate stage belongs to this client (defense-in-depth on top of RLS)
  const { data: stage, error: stageErr } = await supabase
    .from("crm_stages")
    .select("key")
    .eq("client_id", clientId)
    .eq("key", toStage)
    .maybeSingle();
  if (stageErr) return NextResponse.json({ success: false, error: stageErr.message }, { status: 500 });
  if (!stage) {
    return NextResponse.json({ success: false, error: "Unknown stage for this client" }, { status: 400 });
  }

  const { data, error } = await supabase
    .from("crm_leads")
    .update({ stage_key: toStage })
    .eq("id", leadId)
    .eq("client_id", clientId)
    .select("id, stage_key")
    .maybeSingle();

  if (error) return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  if (!data) return NextResponse.json({ success: false, error: "Lead not found" }, { status: 404 });

  return NextResponse.json({ success: true, data });
}
