import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const webhookPayloadSchema = z.object({
  action: z.enum([
    "status_update",
    "invoice_created",
    "invoice_updated",
    "invoice_sent",
    "payment_received",
    "payment_matched",
    "bill_extracted",
    "bill_updated",
    "task_created",
    "task_escalated",
    "task_completed",
    "collection_logged",
    "report_generated",
    "audit_log",
  ]),
  data: z.record(z.string(), z.unknown()),
});

export async function POST(req: NextRequest) {
  const webhookSecret = req.headers.get("x-n8n-webhook-secret");
  // Per-endpoint secret with fallback to the shared one during migration.
  const expectedSecret =
    process.env.N8N_WEBHOOK_SECRET_ACCOUNTING ?? process.env.N8N_WEBHOOK_SECRET;

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
      case "status_update": {
        const d = data as Record<string, unknown>;
        const existing = d.execution_id
          ? await supabase
              .from("acct_workflow_status")
              .select("id")
              .eq("execution_id", d.execution_id as string)
              .eq("client_id", d.client_id as string)
              .maybeSingle()
          : null;

        if (existing?.data?.id) {
          await supabase
            .from("acct_workflow_status")
            .update({
              status: d.status as string,
              step_name: d.step_name as string,
              progress_pct: d.progress_pct as number,
              message: d.message as string,
              error_details: d.error_details as string,
              completed_at: d.status === "completed" ? new Date().toISOString() : null,
              updated_at: new Date().toISOString(),
            })
            .eq("id", existing.data.id);
        } else {
          await supabase.from("acct_workflow_status").insert({
            client_id: d.client_id as string,
            workflow_module: d.workflow_module as string,
            execution_id: d.execution_id as string,
            status: d.status as string,
            step_name: d.step_name as string,
            entity_type: d.entity_type as string,
            entity_id: d.entity_id as string,
            progress_pct: d.progress_pct as number,
            message: d.message as string,
          });
        }
        break;
      }

      case "invoice_created":
      case "invoice_updated": {
        const d = data as Record<string, unknown>;
        const invoiceData: Record<string, unknown> = {
          status: d.status as string,
          updated_at: new Date().toISOString(),
        };
        if (d.pdf_url) invoiceData.pdf_url = d.pdf_url;
        if (d.payment_link) invoiceData.payment_link = d.payment_link;
        if (d.external_id) invoiceData.external_id = d.external_id;
        if (d.amount_paid !== undefined) invoiceData.amount_paid = d.amount_paid;
        if (d.paid_at) invoiceData.paid_at = d.paid_at;

        await supabase
          .from("acct_invoices")
          .update(invoiceData)
          .eq("id", d.invoice_id as string);
        break;
      }

      case "invoice_sent": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("acct_invoices")
          .update({
            status: "sent",
            sent_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.invoice_id as string);
        break;
      }

      case "payment_received": {
        const d = data as Record<string, unknown>;
        await supabase.from("acct_payments").insert({
          client_id: d.client_id as string,
          invoice_id: d.invoice_id as string,
          amount: d.amount as number,
          date_received: (d.date_received as string) ?? new Date().toISOString().split("T")[0],
          method: d.method as string,
          reference_text: d.reference_text as string,
          gateway_transaction_id: d.gateway_transaction_id as string,
          reconciliation_status: (d.reconciliation_status as string) ?? "received",
          match_confidence: d.match_confidence as number,
          pop_url: d.pop_url as string,
        });
        break;
      }

      case "payment_matched": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("acct_payments")
          .update({
            invoice_id: d.invoice_id as string,
            reconciliation_status: d.reconciliation_status as string,
            match_confidence: d.match_confidence as number,
            matched_by: d.matched_by as string,
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.payment_id as string);
        break;
      }

      case "bill_extracted":
      case "bill_updated": {
        const d = data as Record<string, unknown>;
        const billData: Record<string, unknown> = {
          status: d.status as string,
          updated_at: new Date().toISOString(),
        };
        if (d.supplier_id) billData.supplier_id = d.supplier_id;
        if (d.bill_number) billData.bill_number = d.bill_number;
        if (d.bill_date) billData.bill_date = d.bill_date;
        if (d.due_date) billData.due_date = d.due_date;
        if (d.subtotal !== undefined) billData.subtotal = d.subtotal;
        if (d.vat_amount !== undefined) billData.vat_amount = d.vat_amount;
        if (d.total_amount !== undefined) billData.total_amount = d.total_amount;
        if (d.category) billData.category = d.category;
        if (d.ocr_raw) billData.ocr_raw = d.ocr_raw;
        if (d.extraction_confidence !== undefined) billData.extraction_confidence = d.extraction_confidence;
        if (d.external_id) billData.external_id = d.external_id;
        if (d.approver) billData.approver = d.approver;
        if (d.approved_at) billData.approved_at = d.approved_at;
        if (d.payment_status) billData.payment_status = d.payment_status;

        await supabase
          .from("acct_supplier_bills")
          .update(billData)
          .eq("id", d.bill_id as string);
        break;
      }

      case "task_created": {
        const d = data as Record<string, unknown>;
        await supabase.from("acct_tasks").insert({
          client_id: d.client_id as string,
          type: d.type as string,
          priority: (d.priority as string) ?? "medium",
          title: d.title as string,
          description: d.description as string,
          owner: d.owner as string,
          related_entity_type: d.related_entity_type as string,
          related_entity_id: d.related_entity_id as string,
          approval_token: d.approval_token as string,
          due_at: d.due_at as string,
        });
        break;
      }

      case "task_escalated": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("acct_tasks")
          .update({
            status: "escalated",
            escalated_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.task_id as string);
        break;
      }

      case "task_completed": {
        const d = data as Record<string, unknown>;
        await supabase
          .from("acct_tasks")
          .update({
            status: "completed",
            approval_action: d.approval_action as string,
            approval_reason: d.approval_reason as string,
            resolution_notes: d.resolution_notes as string,
            resolved_by: d.resolved_by as string,
            completed_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          })
          .eq("id", d.task_id as string);
        break;
      }

      case "collection_logged": {
        const d = data as Record<string, unknown>;
        await supabase.from("acct_collections").insert({
          client_id: d.client_id as string,
          invoice_id: d.invoice_id as string,
          status: (d.status as string) ?? "sent",
          channel: (d.channel as string) ?? "email",
          template_used: d.template_used as string,
          reminder_tier: (d.reminder_tier as number) ?? 1,
          sent_at: d.sent_at as string,
        });
        break;
      }

      case "report_generated": {
        // Just audit log — reports are generated and emailed by n8n
        const d = data as Record<string, unknown>;
        await supabase.from("acct_audit_log").insert({
          client_id: d.client_id as string,
          event_type: "REPORT_GENERATED",
          entity_type: "report",
          action: d.report_type as string,
          actor: "n8n_wf09",
          result: "success",
          metadata: { report_type: d.report_type, period: d.period },
        });
        break;
      }

      case "audit_log": {
        const d = data as Record<string, unknown>;
        await supabase.from("acct_audit_log").insert({
          client_id: d.client_id as string,
          event_type: d.event_type as string,
          entity_type: d.entity_type as string,
          entity_id: d.entity_id as string,
          action: d.action as string,
          actor: (d.actor as string) ?? "n8n",
          result: (d.result as string) ?? "success",
          error_details: d.error_details as string,
          old_value: d.old_value as Record<string, unknown>,
          new_value: d.new_value as Record<string, unknown>,
          metadata: (d.metadata as Record<string, unknown>) ?? {},
        });
        break;
      }
    }

    return NextResponse.json({ success: true, action });
  } catch (error: unknown) {
    console.error("[webhooks/n8n-accounting] Error:", error);
    return NextResponse.json(
      { error: "Failed to process webhook" },
      { status: 500 }
    );
  }
}
