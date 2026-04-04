import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const scheduleContentSchema = z.object({
  content_id: z.string().uuid(),
  platform: z.enum([
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "tiktok",
    "youtube",
    "threads",
    "bluesky",
    "pinterest",
  ]),
  scheduled_date: z.string(),
  scheduled_time: z.string(),
  timezone: z.string().optional().default("Africa/Johannesburg"),
});

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const url = new URL(req.url);
  const start = url.searchParams.get("start");
  const end = url.searchParams.get("end");

  if (!start || !end) {
    return NextResponse.json(
      { error: "Missing required query params: start, end" },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();
  const { data, error } = await supabase.rpc("mkt_get_content_calendar_range", {
    p_client_id: clientId,
    p_start: start,
    p_end: end,
  });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const body = await req.json();
  const parsed = scheduleContentSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("mkt_content_calendar")
    .insert({
      client_id: clientId,
      content_id: parsed.data.content_id,
      platform: parsed.data.platform,
      scheduled_date: parsed.data.scheduled_date,
      scheduled_time: parsed.data.scheduled_time,
      timezone: parsed.data.timezone,
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // Update content status to scheduled
  await supabase
    .from("mkt_content")
    .update({
      status: "scheduled",
      updated_at: new Date().toISOString(),
    })
    .eq("id", parsed.data.content_id)
    .eq("client_id", clientId);

  return NextResponse.json({ data }, { status: 201 });
}
