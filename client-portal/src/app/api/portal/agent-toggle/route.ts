import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const N8N_WEBHOOK_URL =
  "https://ianimmelman89.app.n8n.cloud/webhook/whatsapp-agent-status";

/**
 * POST /api/portal/agent-toggle
 * Toggle an agent online/offline. Dual-writes to Supabase + Airtable (via n8n webhook).
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { agentId, action } = body as {
    agentId?: string;
    action?: string;
  };

  if (!agentId || !action || !["online", "offline"].includes(action)) {
    return NextResponse.json(
      { error: "Missing or invalid agentId/action" },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify ownership: agent must belong to this client (or user is admin)
  if (session.role === "client") {
    const { data: agent } = await supabase
      .from("agent_profiles")
      .select("id, client_id")
      .eq("agent_id", agentId)
      .single();

    if (!agent || agent.client_id !== session.profileId) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  try {
    // 1. Update Supabase
    const expiry = new Date(Date.now() + 12 * 3600 * 1000).toISOString();
    const { error: dbError } = await supabase
      .from("agent_profiles")
      .update({
        manual_override: action,
        manual_override_expiry: expiry,
        is_online: action === "online",
        updated_at: new Date().toISOString(),
      })
      .eq("agent_id", agentId);

    if (dbError) {
      console.error("Failed to update agent profile:", dbError);
      return NextResponse.json(
        { error: "Failed to update agent" },
        { status: 500 }
      );
    }

    // 2. Sync to Airtable via n8n webhook (fire-and-forget)
    fetch(N8N_WEBHOOK_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        agent_id: agentId,
        status: action,
      }),
    }).catch((err) => {
      console.error("n8n webhook sync failed:", err);
    });

    return NextResponse.json({
      success: true,
      agent_id: agentId,
      status: action,
    });
  } catch (err) {
    console.error("Agent toggle error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
