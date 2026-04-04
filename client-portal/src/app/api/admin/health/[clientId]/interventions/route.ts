import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

interface RouteContext {
  params: Promise<{ clientId: string }>;
}

const createInterventionSchema = z.object({
  intervention_type: z.enum(["email", "call", "task", "offer", "meeting"]),
  notes: z.string().max(2000).optional(),
  assigned_to: z.string().uuid().optional(),
  health_alert_id: z.string().uuid().optional(),
});

export async function GET(_req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }

  const { clientId } = await context.params;
  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("health_interventions")
    .select("*")
    .eq("client_id", clientId)
    .order("created_at", { ascending: false });

  if (error) {
    if (error.code === "42P01") return NextResponse.json([]);
    return NextResponse.json(
      { error: "Failed to load interventions" },
      { status: 500 }
    );
  }

  return NextResponse.json(data ?? []);
}

export async function POST(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Admin access required" }, { status: 403 });
  }

  const { clientId } = await context.params;

  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = createInterventionSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  const { data, error } = await supabase
    .from("health_interventions")
    .insert({
      client_id: clientId,
      intervention_type: parsed.data.intervention_type,
      notes: parsed.data.notes ?? null,
      assigned_to: parsed.data.assigned_to ?? session.profileId,
      health_alert_id: parsed.data.health_alert_id ?? null,
      status: "pending",
      created_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (error) {
    if (error.code === "42P01") {
      return NextResponse.json(
        { error: "Interventions table not yet provisioned" },
        { status: 503 }
      );
    }
    return NextResponse.json(
      { error: "Failed to create intervention" },
      { status: 500 }
    );
  }

  return NextResponse.json(data, { status: 201 });
}
