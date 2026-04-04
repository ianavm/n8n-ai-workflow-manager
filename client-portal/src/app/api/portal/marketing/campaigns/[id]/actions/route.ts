import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const actionSchema = z.object({
  action: z.enum(["pause", "resume", "duplicate", "archive"]),
});

async function notifyN8n(
  clientId: string,
  action: string,
  entityId: string
): Promise<void> {
  const baseUrl = process.env.N8N_BASE_URL;
  if (!baseUrl) return;

  try {
    await fetch(`${baseUrl}/webhook/mkt/portal-action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        client_id: clientId,
        action,
        entity_type: "campaign",
        entity_id: entityId,
      }),
    });
  } catch {
    // n8n may be unreachable; portal continues working
  }
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json(
      { error: "Client access required" },
      { status: 403 }
    );
  }

  const body = await req.json();
  const parsed = actionSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();
  const { action } = parsed.data;

  // -- Pause ---------------------------------------------------------------
  if (action === "pause") {
    const { data, error } = await supabase
      .from("mkt_campaigns")
      .update({
        status: "paused",
        updated_at: new Date().toISOString(),
      })
      .eq("id", id)
      .eq("client_id", clientId)
      .eq("status", "active")
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    if (data?.platform_campaign_id) {
      await notifyN8n(clientId, "pause_campaign", id);
    }

    return NextResponse.json({ success: true, data });
  }

  // -- Resume --------------------------------------------------------------
  if (action === "resume") {
    const { data, error } = await supabase
      .from("mkt_campaigns")
      .update({
        status: "active",
        updated_at: new Date().toISOString(),
      })
      .eq("id", id)
      .eq("client_id", clientId)
      .eq("status", "paused")
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    if (data?.platform_campaign_id) {
      await notifyN8n(clientId, "resume_campaign", id);
    }

    return NextResponse.json({ success: true, data });
  }

  // -- Duplicate -----------------------------------------------------------
  if (action === "duplicate") {
    const { data: original, error: fetchErr } = await supabase
      .from("mkt_campaigns")
      .select("*")
      .eq("id", id)
      .eq("client_id", clientId)
      .single();

    if (fetchErr || !original) {
      return NextResponse.json(
        { error: fetchErr?.message ?? "Campaign not found" },
        { status: fetchErr ? 500 : 404 }
      );
    }

    const { data: copy, error: insertErr } = await supabase
      .from("mkt_campaigns")
      .insert({
        client_id: original.client_id,
        name: `${original.name} (Copy)`,
        platform: original.platform,
        campaign_type: original.campaign_type,
        status: "draft",
        budget_total: original.budget_total,
        budget_daily: original.budget_daily,
        budget_spent: 0,
        targeting: original.targeting,
        start_date: original.start_date,
        end_date: original.end_date,
        notes: original.notes,
        platform_campaign_id: null,
        performance_summary: null,
        created_by: session.email,
      })
      .select()
      .single();

    if (insertErr) {
      return NextResponse.json({ error: insertErr.message }, { status: 500 });
    }

    return NextResponse.json({ success: true, data: copy }, { status: 201 });
  }

  // -- Archive -------------------------------------------------------------
  if (action === "archive") {
    const { data, error } = await supabase
      .from("mkt_campaigns")
      .update({
        status: "archived",
        updated_at: new Date().toISOString(),
      })
      .eq("id", id)
      .eq("client_id", clientId)
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true, data });
  }

  return NextResponse.json({ error: "Unknown action" }, { status: 400 });
}
