import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

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

  // Fetch meeting to verify access
  const { data: meeting, error: meetingError } = await supabase
    .from("fa_meetings")
    .select("id, client_id, firm_id")
    .eq("id", id)
    .single();

  if (meetingError || !meeting) {
    return NextResponse.json({ error: "Meeting not found" }, { status: 404 });
  }

  // Access control
  if (session.role === "client" && session.faClientId !== meeting.client_id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  if (
    ["adviser", "compliance_officer"].includes(session.role) &&
    meeting.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const { data: insights, error } = await supabase
    .from("fa_meeting_insights")
    .select("*")
    .eq("meeting_id", id)
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch insights" },
      { status: 500 }
    );
  }

  // Strip compliance_flags for client role
  const result =
    session.role === "client"
      ? (insights ?? []).map(
          ({ compliance_flags: _cf, ...rest }: Record<string, unknown>) => rest
        )
      : (insights ?? []);

  return NextResponse.json({ success: true, data: result });
}
