import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const updateLeadSchema = z.object({
  first_name: z.string().max(100).optional(),
  last_name: z.string().max(100).optional(),
  email: z.string().email().max(255).optional(),
  phone: z.string().max(30).optional(),
  company: z.string().max(200).optional(),
  stage: z.string().min(1).max(50).optional(),
  score: z.number().int().min(0).max(100).optional(),
  assigned_agent: z.string().max(200).optional(),
  tags: z.array(z.string().max(50)).optional(),
  notes: z.string().max(5000).optional(),
  conversion_value: z.number().int().min(0).optional(),
  lost_reason: z.string().max(500).optional(),
});

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { id } = await params;
  const supabase = await createServiceRoleClient();

  const { data: lead, error: leadError } = await supabase
    .from("mkt_leads")
    .select("*")
    .eq("id", id)
    .eq("client_id", clientId)
    .single();

  if (leadError || !lead) {
    return NextResponse.json({ error: "Lead not found" }, { status: 404 });
  }

  const { data: activities } = await supabase
    .from("mkt_lead_activities")
    .select("*")
    .eq("lead_id", id)
    .order("created_at", { ascending: false })
    .limit(10);

  return NextResponse.json({ lead, activities: activities ?? [] });
}

export async function PATCH(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { id } = await params;
  const body = await req.json();
  const parsed = updateLeadSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();
  const { data, error } = await supabase
    .from("mkt_leads")
    .update({
      ...parsed.data,
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("client_id", clientId)
    .select()
    .single();

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  if (!data) {
    return NextResponse.json({ error: "Lead not found" }, { status: 404 });
  }

  return NextResponse.json({ data });
}
