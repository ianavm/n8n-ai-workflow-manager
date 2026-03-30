import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const webhookPayloadSchema = z.object({
  action: z.enum([
    "meeting_created",
    "meeting_completed",
    "insights_ready",
    "task_created",
    "communication_sent",
    "document_classified",
    "pipeline_updated",
  ]),
  data: z.record(z.string(), z.unknown()),
});

export async function POST(req: NextRequest) {
  // Validate webhook secret
  const webhookSecret = req.headers.get("x-n8n-webhook-secret");
  const expectedSecret = process.env.N8N_WEBHOOK_SECRET;

  if (!expectedSecret || webhookSecret !== expectedSecret) {
    return NextResponse.json({ error: "Invalid webhook secret" }, { status: 401 });
  }

  const body = await req.json();
  const parsed = webhookPayloadSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const { action, data } = parsed.data;
  const supabase = await createServiceRoleClient();

  try {
    switch (action) {
      case "meeting_created": {
        const meetingData = data as Record<string, unknown>;
        await supabase
          .from("fa_meetings")
          .update({
            status: "confirmed",
            calendar_event_id: meetingData.calendar_event_id as string,
            video_link: meetingData.video_link as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", meetingData.meeting_id as string);
        break;
      }

      case "meeting_completed": {
        const completedData = data as Record<string, unknown>;
        await supabase
          .from("fa_meetings")
          .update({
            status: "completed",
            outcome_summary: completedData.summary as string,
            recording_url: completedData.recording_url as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", completedData.meeting_id as string);
        break;
      }

      case "insights_ready": {
        const insightsData = data as Record<string, unknown>;
        await supabase.from("fa_meeting_insights").insert({
          meeting_id: insightsData.meeting_id as string,
          firm_id: insightsData.firm_id as string,
          summary: insightsData.summary as string,
          action_items: insightsData.action_items,
          risk_factors: insightsData.risk_factors,
          compliance_flags: insightsData.compliance_flags,
          sentiment_score: insightsData.sentiment_score as number,
          topics_discussed: insightsData.topics_discussed,
        });
        break;
      }

      case "task_created": {
        const taskData = data as Record<string, unknown>;
        await supabase.from("fa_tasks").insert({
          firm_id: taskData.firm_id as string,
          client_id: taskData.client_id as string,
          title: taskData.title as string,
          description: taskData.description as string,
          type: (taskData.type as string) ?? "general",
          priority: (taskData.priority as string) ?? "medium",
          status: "pending",
          due_date: taskData.due_date as string,
          assigned_to: taskData.assigned_to as string,
          created_by: "n8n_webhook",
        });
        break;
      }

      case "communication_sent": {
        const commData = data as Record<string, unknown>;
        await supabase.from("fa_communications").insert({
          firm_id: commData.firm_id as string,
          client_id: commData.client_id as string,
          channel: commData.channel as string,
          direction: (commData.direction as string) ?? "outbound",
          subject: commData.subject as string,
          body: commData.body as string,
          sent_by: commData.sent_by as string,
          sent_at: commData.sent_at as string,
        });
        break;
      }

      case "document_classified": {
        const docData = data as Record<string, unknown>;
        await supabase
          .from("fa_documents")
          .update({
            category: docData.category as string,
            ai_classification: docData.classification,
            updated_at: new Date().toISOString(),
          })
          .eq("id", docData.document_id as string);
        break;
      }

      case "pipeline_updated": {
        const pipelineData = data as Record<string, unknown>;
        await supabase
          .from("fa_clients")
          .update({
            pipeline_stage: pipelineData.pipeline_stage as string,
            health_score: pipelineData.health_score as number,
            pipeline_stage_changed_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq("id", pipelineData.client_id as string);
        break;
      }
    }

    return NextResponse.json({ success: true, action });
  } catch {
    return NextResponse.json(
      { error: "Failed to process webhook" },
      { status: 500 }
    );
  }
}
