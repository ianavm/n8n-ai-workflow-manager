import { NextRequest, NextResponse } from "next/server";
import Papa from "papaparse";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import { ingestCsvBatch } from "@/lib/crm/csv-ingest";
import type { CrmTargetField } from "@/lib/crm/csv-mapping";

export const runtime = "nodejs";
export const maxDuration = 60;

const ALLOWED_FIELDS: ReadonlyArray<CrmTargetField> = [
  "company_name",
  "company_domain",
  "company_industry",
  "company_country",
  "company_size_band",
  "company_revenue_band",
  "company_website",
  "company_linkedin_url",
  "company_hq_city",
  "contact_first_name",
  "contact_last_name",
  "contact_full_name",
  "contact_title",
  "contact_email",
  "contact_phone",
  "contact_linkedin_url",
  "lead_stage_key",
  "lead_score",
  "lead_source",
  "lead_tags",
  "lead_deal_value",
  "lead_deal_probability",
  "lead_next_action",
  "lead_next_action_at",
];

const bodySchema = z.object({
  mapping: z.record(z.string(), z.union([z.enum(ALLOWED_FIELDS as [string, ...string[]]), z.null()])),
  defaultStageKey: z.string().trim().min(1).max(64).default("new"),
});

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params;
  const body = await req.json().catch(() => null);
  const parsed = bodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid body" }, { status: 400 });
  }
  const mapping = parsed.data.mapping as Record<string, CrmTargetField | null>;

  const ctx = await getCrmViewerContext();
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json({ success: false, error: "Admin must pass client" }, { status: 400 });
  }

  // Require at least company_name OR contact_email to be mapped
  const mappedFields = new Set(Object.values(mapping).filter(Boolean) as CrmTargetField[]);
  if (!mappedFields.has("company_name") && !mappedFields.has("contact_email") && !mappedFields.has("contact_full_name")) {
    return NextResponse.json(
      {
        success: false,
        error:
          "Map at least one of: Company name, Contact email, or Full name — otherwise rows can't be identified.",
      },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();
  const { data: importRow, error: fetchErr } = await supabase
    .from("crm_imports")
    .select("id, storage_path, status")
    .eq("id", id)
    .eq("client_id", clientId)
    .maybeSingle();
  if (fetchErr) return NextResponse.json({ success: false, error: fetchErr.message }, { status: 500 });
  if (!importRow) return NextResponse.json({ success: false, error: "Import not found" }, { status: 404 });
  if (importRow.status === "completed") {
    return NextResponse.json(
      { success: false, error: "Import already ingested" },
      { status: 409 },
    );
  }

  // Validate default stage belongs to this client
  const { data: stage } = await supabase
    .from("crm_stages")
    .select("key")
    .eq("client_id", clientId)
    .eq("key", parsed.data.defaultStageKey)
    .maybeSingle();
  if (!stage) {
    return NextResponse.json(
      { success: false, error: "Default stage does not belong to this client" },
      { status: 400 },
    );
  }

  // Mark ingesting, persist final mapping
  await supabase
    .from("crm_imports")
    .update({ status: "ingesting", field_mapping: mapping })
    .eq("id", id);

  // Download CSV from Storage
  const { data: blob, error: dlErr } = await supabase.storage
    .from("crm-imports")
    .download(importRow.storage_path);
  if (dlErr || !blob) {
    await supabase
      .from("crm_imports")
      .update({ status: "failed", error_message: `Download failed: ${dlErr?.message ?? "no blob"}` })
      .eq("id", id);
    return NextResponse.json(
      { success: false, error: dlErr?.message ?? "Download failed" },
      { status: 500 },
    );
  }

  const csvText = await blob.text();
  const parsedCsv = Papa.parse<Record<string, string>>(csvText, {
    header: true,
    skipEmptyLines: "greedy",
    transformHeader: (h) => h.trim(),
  });

  const result = await ingestCsvBatch({
    supabase,
    clientId,
    importId: id,
    rows: parsedCsv.data,
    mapping,
    defaultStageKey: parsed.data.defaultStageKey,
  });

  await supabase
    .from("crm_imports")
    .update({
      status: result.failed === parsedCsv.data.length ? "failed" : "completed",
      rows_total: parsedCsv.data.length,
      rows_ingested: result.ingested,
      rows_failed: result.failed,
      error_message: result.errors.length > 0 ? summarizeErrors(result.errors) : null,
      completed_at: new Date().toISOString(),
    })
    .eq("id", id);

  return NextResponse.json({ success: true, data: result });
}

function summarizeErrors(errors: Array<{ row: number; reason: string }>): string {
  const sample = errors.slice(0, 3).map((e) => `row ${e.row}: ${e.reason}`).join("; ");
  const suffix = errors.length > 3 ? ` …and ${errors.length - 3} more` : "";
  return sample + suffix;
}
