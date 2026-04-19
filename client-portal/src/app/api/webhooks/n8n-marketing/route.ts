import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const webhookPayloadSchema = z.object({
  action: z.enum([
    "content_posted",
    "content_failed",
    "content_scheduled",
    "performance_sync",
    "lead_captured",
    "campaign_updated",
    "task_created",
  ]),
  data: z.record(z.string(), z.unknown()),
});

export async function POST(req: NextRequest) {
  const webhookSecret = req.headers.get("x-n8n-webhook-secret");
  // Per-endpoint secret with fallback to the shared one during migration.
  const expectedSecret =
    process.env.N8N_WEBHOOK_SECRET_MARKETING ?? process.env.N8N_WEBHOOK_SECRET;

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
      case "content_posted": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("mkt_content_calendar")
          .update({
            status: "posted",
            posted_at: new Date().toISOString(),
            platform_post_id: d.platform_post_id as string,
            post_url: d.post_url as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.calendar_id as string);

        await supabase
          .from("mkt_content")
          .update({
            status: "posted",
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.content_id as string);
        break;
      }

      case "content_failed": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("mkt_content_calendar")
          .update({
            status: "failed",
            error_message: d.error_message as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.calendar_id as string);

        await supabase
          .from("mkt_content")
          .update({
            status: "failed",
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.content_id as string);
        break;
      }

      case "content_scheduled": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("mkt_content_calendar")
          .update({
            status: "queued",
            blotato_post_id: d.blotato_post_id as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.calendar_id as string);
        break;
      }

      case "performance_sync": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("mkt_performance")
          .upsert(
            {
              client_id: d.client_id as string,
              campaign_id: d.campaign_id as string,
              ad_id: d.ad_id as string,
              date: d.date as string,
              platform: d.platform as string,
              impressions: d.impressions as number,
              clicks: d.clicks as number,
              spend: d.spend as number,
              conversions: d.conversions as number,
              conversion_value: d.conversion_value as number,
              leads_generated: d.leads_generated as number,
              ctr: d.ctr as number,
              cpc: d.cpc as number,
              cpl: d.cpl as number,
              cpa: d.cpa as number,
              roas: d.roas as number,
              reach: d.reach as number,
              frequency: d.frequency as number,
              video_views: d.video_views as number,
              engagement: d.engagement as number,
            },
            { onConflict: "campaign_id,ad_id,date,platform" }
          );

        await supabase
          .from("mkt_campaigns")
          .update({
            budget_spent: d.total_spent as number,
            performance_summary: d.summary as Record<string, unknown>,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.campaign_id as string);
        break;
      }

      case "lead_captured": {
        const d = data as Record<string, unknown>;
        const fullName = (d.name as string) ?? "";
        const nameParts = fullName.split(" ");
        const { data: lead } = await supabase
          .from("mkt_leads")
          .insert({
            client_id: d.client_id as string,
            first_name: (d.first_name as string) ?? (nameParts[0] ?? null),
            last_name: (d.last_name as string) ?? (nameParts.slice(1).join(" ") || null),
            email: d.email as string,
            phone: d.phone as string,
            company: d.company as string,
            source: (d.source as string) ?? "other",
            source_detail: d.source_detail as string,
            campaign_id: d.campaign_id as string,
            stage: (d.stage as string) ?? "new",
            score: (d.score as number) ?? 0,
            utm_source: d.utm_source as string,
            utm_medium: d.utm_medium as string,
            utm_campaign: d.utm_campaign as string,
            custom_fields: (d.custom_fields as Record<string, unknown>) ?? {},
          })
          .select()
          .single();

        if (lead) {
          await supabase.from("mkt_lead_activities").insert({
            client_id: d.client_id as string,
            lead_id: lead.id,
            activity_type: "system",
            title: `Lead captured via ${(d.source as string) ?? "webhook"}`,
            actor: "n8n",
          });
        }
        break;
      }

      case "campaign_updated": {
        const d = data as Record<string, unknown>;
        const rawUpdates = (d.updates ?? {}) as Record<string, unknown>;
        const ALLOWED_CAMPAIGN_UPDATE_KEYS = new Set([
          "status",
          "budget_spent",
          "performance_summary",
          "end_date",
          "impressions",
          "clicks",
          "conversions",
        ]);
        const safeUpdates: Record<string, unknown> = {};
        for (const [key, val] of Object.entries(rawUpdates)) {
          if (ALLOWED_CAMPAIGN_UPDATE_KEYS.has(key)) safeUpdates[key] = val;
        }
        await supabase
          .from("mkt_campaigns")
          .update({
            ...safeUpdates,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.campaign_id as string);
        break;
      }

      case "task_created": {
        const d = data as Record<string, unknown>;
        await supabase.from("mkt_tasks").insert({
          client_id: d.client_id as string,
          type: d.type as string,
          priority: (d.priority as string) ?? "medium",
          title: d.title as string,
          description: d.description as string,
          assignee: d.assignee as string,
          due_date: d.due_date as string,
          related_entity_type: d.related_entity_type as string,
          related_entity_id: d.related_entity_id as string,
        });
        break;
      }
    }

    return NextResponse.json({ success: true, action });
  } catch (error: unknown) {
    console.error("[webhooks/n8n-marketing] Error:", error);
    return NextResponse.json(
      { error: "Failed to process webhook" },
      { status: 500 }
    );
  }
}
