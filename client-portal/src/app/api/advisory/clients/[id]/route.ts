import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const clientUpdateSchema = z.object({
  first_name: z.string().min(1).optional(),
  last_name: z.string().min(1).optional(),
  email: z.string().email().optional(),
  phone: z.string().optional(),
  mobile: z.string().optional(),
  id_number: z.string().optional(),
  date_of_birth: z.string().optional(),
  tax_number: z.string().optional(),
  physical_address: z.string().optional(),
  postal_address: z.string().optional(),
  employer: z.string().optional(),
  occupation: z.string().optional(),
  source: z.string().optional(),
  pipeline_stage: z.string().optional(),
  health_score: z.number().min(0).max(100).optional(),
  notes: z.string().optional(),
});

const CLIENT_EDITABLE_FIELDS = [
  "phone",
  "mobile",
  "physical_address",
  "postal_address",
] as const;

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

  // Clients can only access their own record
  if (session.role === "client") {
    if (session.faClientId !== id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
  }

  const { data, error } = await supabase
    .from("fa_clients")
    .select(
      "*"
    )
    .eq("id", id)
    .single();

  if (error || !data) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Advisers can only access clients in their firm
  if (
    ["adviser", "compliance_officer"].includes(session.role) &&
    data.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  return NextResponse.json({ success: true, data });
}

export async function PATCH(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const body = await req.json();
  const parsed = clientUpdateSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify client exists and check access
  const { data: existing, error: fetchError } = await supabase
    .from("fa_clients")
    .select("id, firm_id")
    .eq("id", id)
    .single();

  if (fetchError || !existing) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Build update payload based on role
  let updateData: Record<string, unknown>;

  if (session.role === "client") {
    if (session.faClientId !== id) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
    // Clients can only update limited fields
    updateData = {};
    for (const field of CLIENT_EDITABLE_FIELDS) {
      if (parsed.data[field] !== undefined) {
        updateData[field] = parsed.data[field];
      }
    }
    if (Object.keys(updateData).length === 0) {
      return NextResponse.json(
        { error: "No editable fields provided" },
        { status: 400 }
      );
    }
  } else {
    // Advisers: check firm match
    if (
      ["adviser", "compliance_officer"].includes(session.role) &&
      existing.firm_id !== session.firmId
    ) {
      return NextResponse.json({ error: "Forbidden" }, { status: 403 });
    }
    updateData = { ...parsed.data };
  }

  updateData.updated_at = new Date().toISOString();

  const { data, error } = await supabase
    .from("fa_clients")
    .update(updateData)
    .eq("id", id)
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to update client" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: existing.firm_id,
    performed_by: session.id,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "updated",
    entity_type: "fa_clients",
    entity_id: id,
    new_value: { updated_fields: Object.keys(updateData) },
  });

  return NextResponse.json({ success: true, data });
}
