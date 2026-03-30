import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();

  try {
    // Client role: return their personal dashboard
    if (session.role === "client") {
      if (!session.faClientId) {
        return NextResponse.json(
          { error: "No advisory client profile linked" },
          { status: 403 }
        );
      }

      const { data, error } = await supabase.rpc("fa_get_client_dashboard", {
        p_client_id: session.faClientId,
      });

      if (error) {
        return NextResponse.json(
          { error: "Failed to fetch client dashboard" },
          { status: 500 }
        );
      }

      return NextResponse.json({ success: true, data });
    }

    // Adviser / compliance_officer / owner: return pipeline summary + aggregates
    if (!session.firmId) {
      return NextResponse.json(
        { error: "No firm associated with account" },
        { status: 403 }
      );
    }

    const [pipelineResult, clientsResult, meetingsResult, tasksResult] =
      await Promise.all([
        supabase.rpc("fa_get_pipeline_summary", {
          p_firm_id: session.firmId,
        }),
        supabase
          .from("fa_clients")
          .select("id, pipeline_stage, health_score", { count: "exact" })
          .eq("firm_id", session.firmId),
        supabase
          .from("fa_meetings")
          .select("id, status", { count: "exact" })
          .eq("firm_id", session.firmId)
          .gte(
            "scheduled_at",
            new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString()
          ),
        supabase
          .from("fa_tasks")
          .select("id, status", { count: "exact" })
          .eq("firm_id", session.firmId)
          .eq("status", "pending"),
      ]);

    if (pipelineResult.error) {
      return NextResponse.json(
        { error: "Failed to fetch pipeline summary" },
        { status: 500 }
      );
    }

    const clients = clientsResult.data ?? [];
    const avgHealth =
      clients.length > 0
        ? Math.round(
            clients.reduce((sum, c) => sum + (c.health_score ?? 0), 0) /
              clients.length
          )
        : 0;

    return NextResponse.json({
      success: true,
      data: {
        pipeline: pipelineResult.data,
        totalClients: clientsResult.count ?? 0,
        averageHealthScore: avgHealth,
        meetingsThisWeek: meetingsResult.count ?? 0,
        pendingTasks: tasksResult.count ?? 0,
      },
    });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
