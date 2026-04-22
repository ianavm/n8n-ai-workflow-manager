import { NextRequest, NextResponse } from "next/server";
import Papa from "papaparse";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";
import { autoDetectMapping } from "@/lib/crm/csv-mapping";

export const runtime = "nodejs";

const MAX_BYTES = 10 * 1024 * 1024; // 10 MB — matches bucket limit
const MAX_ROWS = 10_000;
const PREVIEW_ROWS = 10;

/**
 * POST /api/crm/imports
 *
 * multipart/form-data, field name = "file".
 *
 * Uploads the CSV to Supabase Storage ("crm-imports" bucket) under
 * {client_id}/{import_id}/{filename}, creates a crm_imports row, parses headers
 * + first N rows, auto-detects a field mapping, and returns preview + mapping
 * for the client to confirm.
 */
export async function POST(req: NextRequest) {
  const ctx = await getCrmViewerContext();
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass ?client=<uuid> for now" },
      { status: 400 },
    );
  }

  const form = await req.formData().catch(() => null);
  const file = form?.get("file");
  if (!(file instanceof File)) {
    return NextResponse.json({ success: false, error: "No file uploaded (field 'file')" }, { status: 400 });
  }
  if (file.size === 0) {
    return NextResponse.json({ success: false, error: "File is empty" }, { status: 400 });
  }
  if (file.size > MAX_BYTES) {
    return NextResponse.json(
      { success: false, error: `File too large (max ${MAX_BYTES / 1024 / 1024} MB)` },
      { status: 413 },
    );
  }

  const rawText = await file.text();
  const parsed = Papa.parse<Record<string, string>>(rawText, {
    header: true,
    skipEmptyLines: "greedy",
    dynamicTyping: false,
    transformHeader: (h) => h.trim(),
  });

  if (parsed.errors.length > 0 && !parsed.data.length) {
    return NextResponse.json(
      { success: false, error: `CSV parse failed: ${parsed.errors[0].message}` },
      { status: 400 },
    );
  }

  const totalRows = parsed.data.length;
  if (totalRows === 0) {
    return NextResponse.json({ success: false, error: "No data rows found in CSV" }, { status: 400 });
  }
  if (totalRows > MAX_ROWS) {
    return NextResponse.json(
      { success: false, error: `Too many rows (max ${MAX_ROWS.toLocaleString()})` },
      { status: 413 },
    );
  }

  const headers = (parsed.meta.fields ?? []).filter(Boolean);
  const mapping = autoDetectMapping(headers);
  const preview = parsed.data.slice(0, PREVIEW_ROWS);

  const supabase = await createServerSupabaseClient();

  // Create the import row in 'pending' state
  const { data: importRow, error: insertErr } = await supabase
    .from("crm_imports")
    .insert({
      client_id: clientId,
      filename: file.name,
      storage_path: "pending",
      status: "pending",
      rows_total: totalRows,
      field_mapping: mapping,
    })
    .select("id")
    .single();

  if (insertErr || !importRow) {
    return NextResponse.json(
      { success: false, error: insertErr?.message ?? "Failed to create import record" },
      { status: 500 },
    );
  }

  // Upload to Storage
  const storagePath = `${clientId}/${importRow.id}/${file.name}`;
  const { error: uploadErr } = await supabase.storage
    .from("crm-imports")
    .upload(storagePath, file, { cacheControl: "3600", upsert: false, contentType: "text/csv" });

  if (uploadErr) {
    await supabase
      .from("crm_imports")
      .update({ status: "failed", error_message: `Storage upload failed: ${uploadErr.message}` })
      .eq("id", importRow.id);
    return NextResponse.json({ success: false, error: uploadErr.message }, { status: 500 });
  }

  await supabase.from("crm_imports").update({ storage_path: storagePath }).eq("id", importRow.id);

  return NextResponse.json({
    success: true,
    data: {
      importId: importRow.id,
      headers,
      mapping,
      preview,
      rowsTotal: totalRows,
    },
  });
}
