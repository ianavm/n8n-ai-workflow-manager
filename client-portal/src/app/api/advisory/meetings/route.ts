import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const createMeetingSchema = z.object({
  client_id: z.string().uuid("Valid client ID is required"),
  type: z.enum([
    "initial_consultation",
    "annual_review",
    "ad_hoc",
    "claims",
    "onboarding",
  ]),
  scheduled_at: z.string().min(1, "Scheduled date is required"),
  duration_minutes: z.number().int().min(15).max(480).default(60),
  location: z.string().optional(),
  video_link: z.string().url().optional(),
  agenda: z.string().optional(),
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

  let query = supabase
    .from("fa_meetings")
    .select(
      "*, client:fa_clients!fa_meetings_client_id_fkey(id, first_name, last_name, email), adviser:fa_advisers!fa_meetings_adviser_id_fkey(id, full_name)"
    )
    .order("scheduled_at", { ascending: false });

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

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch meetings" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data: data ?? [] });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "owner"].includes(session.role)
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
  const parsed = createMeetingSchema.safeParse(body);

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
    .select("id, firm_id")
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
    .from("fa_meetings")
    .insert({
      ...parsed.data,
      firm_id: session.firmId,
      adviser_id: session.adviserId ?? session.profileId,
      status: "scheduled",
      created_by: session.profileId,
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to create meeting" },
      { status: 500 }
    );
  }

  // Trigger n8n webhook for booking
  const webhookUrl = process.env.N8N_WEBHOOK_MEETING_CREATED;
  if (webhookUrl) {
    fetch(webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action: "meeting_created",
        meeting_id: data.id,
        client_id: parsed.data.client_id,
        adviser_id: session.adviserId,
        scheduled_at: parsed.data.scheduled_at,
        type: parsed.data.type,
      }),
    }).catch(() => {
      // Non-blocking webhook; failure is logged but not surfaced
    });
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: session.firmId,
    actor_id: session.profileId,
    actor_type: session.role,
    action: "meeting_created",
    entity_type: "fa_meetings",
    entity_id: data.id,
    details: { type: parsed.data.type, client_id: parsed.data.client_id },
  });

  return NextResponse.json({ success: true, data }, { status: 201 });
}
