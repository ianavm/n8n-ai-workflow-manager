import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Must be an adviser-type role
  if (
    !["adviser", "compliance_officer", "office_manager", "super_admin", "staff_admin"].includes(
      session.role
    )
  ) {
    return NextResponse.json(
      { error: "Forbidden: Adviser access required" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();

  try {
    // Determine which adviser to query
    const queryAdviserId = request.nextUrl.searchParams.get("adviser_id");
    let adviserId: string;

    if (queryAdviserId) {
      // Only office_manager, super_admin, owner can view other advisers
      if (
        !["office_manager", "super_admin", "staff_admin"].includes(session.role)
      ) {
        return NextResponse.json(
          { error: "Forbidden: Cannot view other adviser dashboards" },
          { status: 403 }
        );
      }
      adviserId = queryAdviserId;
    } else {
      if (!session.adviserId) {
        return NextResponse.json(
          { error: "No adviser profile linked to account" },
          { status: 403 }
        );
      }
      adviserId = session.adviserId;
    }

    // Fetch the main dashboard RPC
    const { data: dashboard, error: dashError } = await supabase.rpc(
      "fa_get_adviser_dashboard",
      { p_adviser_id: adviserId }
    );

    if (dashError) {
      return NextResponse.json(
        { error: "Failed to fetch adviser dashboard" },
        { status: 500 }
      );
    }

    // Fetch supplementary data in parallel
    const [recentMeetings, upcomingMeetings, overdueTasks] = await Promise.all([
      // Last 5 completed/cancelled meetings
      supabase
        .from("fa_meetings")
        .select(
          "id, title, scheduled_at, ended_at, status, meeting_type, fa_clients!inner(id, first_name, last_name)"
        )
        .eq("adviser_id", adviserId)
        .in("status", ["completed", "cancelled", "no_show"])
        .order("scheduled_at", { ascending: false })
        .limit(5),

      // Next 5 upcoming meetings
      supabase
        .from("fa_meetings")
        .select(
          "id, title, scheduled_at, status, meeting_type, location, teams_meeting_url, fa_clients!inner(id, first_name, last_name)"
        )
        .eq("adviser_id", adviserId)
        .in("status", ["scheduled", "confirmed"])
        .gte("scheduled_at", new Date().toISOString())
        .order("scheduled_at", { ascending: true })
        .limit(5),

      // Top 5 overdue tasks
      supabase
        .from("fa_tasks")
        .select(
          "id, title, due_date, priority, status, fa_clients!inner(id, first_name, last_name)"
        )
        .eq("assigned_to", adviserId)
        .lt("due_date", new Date().toISOString())
        .not("status", "in", "(completed,cancelled)")
        .order("due_date", { ascending: true })
        .limit(5),
    ]);

    return NextResponse.json({
      success: true,
      data: {
        ...dashboard,
        recent_meetings: recentMeetings.data ?? [],
        upcoming_meetings_list: upcomingMeetings.data ?? [],
        overdue_tasks_list: overdueTasks.data ?? [],
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
