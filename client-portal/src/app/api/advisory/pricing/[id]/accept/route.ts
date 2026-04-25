import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface RouteContext {
  params: Promise<{ id: string }>;
}

export async function POST(req: NextRequest, context: RouteContext) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await context.params;
  const supabase = await createServiceRoleClient();

  // Fetch pricing record
  const { data: pricing, error: fetchError } = await supabase
    .from("fa_pricing")
    .select("id, client_id, firm_id, accepted_by_client, locked_at")
    .eq("id", id)
    .single();

  if (fetchError || !pricing) {
    return NextResponse.json(
      { error: "Pricing record not found" },
      { status: 404 }
    );
  }

  // Only the linked client can accept pricing
  if (session.role === "client" && session.faClientId !== pricing.client_id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Advisers/owners can also accept on behalf of clients in their firm
  if (
    ["adviser", "compliance_officer", "staff_admin"].includes(session.role) &&
    pricing.firm_id !== session.firmId
  ) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  // Prevent double-acceptance
  if (pricing.locked_at) {
    return NextResponse.json(
      { error: "Pricing has already been accepted and locked" },
      { status: 409 }
    );
  }

  const now = new Date().toISOString();

  // Update pricing record
  const { data, error: updateError } = await supabase
    .from("fa_pricing")
    .update({
      accepted_by_client: true,
      accepted_at: now,
      locked_at: now,
      updated_at: now,
    })
    .eq("id", id)
    .select()
    .single();

  if (updateError) {
    return NextResponse.json(
      { error: "Failed to accept pricing" },
      { status: 500 }
    );
  }

  // Record consent
  const ipAddress =
    req.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ??
    req.headers.get("x-real-ip") ??
    "unknown";

  await supabase.from("fa_consent_records").insert({
    firm_id: pricing.firm_id,
    client_id: pricing.client_id,
    consent_type: "fais_record_of_advice",
    granted: true,
    granted_at: now,
    ip_address: ipAddress,
    user_agent: req.headers.get("user-agent") ?? "unknown",
  });

  // Audit log with IP
  await supabase.from("fa_audit_log").insert({
    firm_id: pricing.firm_id,
    performed_by: session.profileId,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "fee_accepted",
    entity_type: "fa_pricing",
    entity_id: id,
    new_value: {
      client_id: pricing.client_id,
      ip_address: ipAddress,
      accepted_at: now,
    },
  });

  return NextResponse.json({ success: true, data });
}
