import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const createClientSchema = z.object({
  first_name: z.string().min(1, "First name is required"),
  last_name: z.string().min(1, "Last name is required"),
  email: z.string().email("Valid email is required"),
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
  pipeline_stage: z.string().default("lead"),
  assigned_adviser_id: z.string().uuid().optional(),
  notes: z.string().optional(),
});

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "owner"].includes(session.role)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!session.firmId) {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();
  const { searchParams } = new URL(req.url);
  const search = searchParams.get("search") ?? "";
  const pipelineStage = searchParams.get("pipeline_stage") ?? "";

  let query = supabase
    .from("fa_clients")
    .select(
      "*, assigned_adviser:fa_advisers!fa_clients_assigned_adviser_id_fkey(id, full_name)"
    )
    .eq("firm_id", session.firmId)
    .order("created_at", { ascending: false });

  if (pipelineStage) {
    query = query.eq("pipeline_stage", pipelineStage);
  }

  if (search) {
    query = query.or(
      `first_name.ilike.%${search}%,last_name.ilike.%${search}%,email.ilike.%${search}%`
    );
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch clients" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data: data ?? [] });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "owner"].includes(session.role)
  ) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (!session.firmId) {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const body = await req.json();
  const parsed = createClientSchema.safeParse(body);

  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("fa_clients")
    .insert({
      ...parsed.data,
      firm_id: session.firmId,
      assigned_adviser_id:
        parsed.data.assigned_adviser_id ?? session.adviserId ?? null,
      created_by: session.profileId,
    })
    .select()
    .single();

  if (error) {
    return NextResponse.json(
      { error: "Failed to create client" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: session.firmId,
    actor_id: session.profileId,
    actor_type: session.role,
    action: "client_created",
    entity_type: "fa_clients",
    entity_id: data.id,
    details: { email: parsed.data.email },
  });

  return NextResponse.json({ success: true, data }, { status: 201 });
}
