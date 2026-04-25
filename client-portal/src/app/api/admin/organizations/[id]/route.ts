import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { getSession, isAdmin } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const patchSchema = z.object({
  seat_limit: z.number().int().min(1).max(500).optional(),
  status: z.enum(["active", "suspended", "inactive"]).optional(),
  company_name: z.string().trim().min(1).max(200).optional(),
});

interface RouteContext {
  params: Promise<{ id: string }>;
}

/**
 * PATCH /api/admin/organizations/[id]
 * Admin-only. Updates org-level fields — seat limit, status, company name.
 * Audit-logged so account-lifecycle changes can be traced.
 */
export async function PATCH(request: NextRequest, ctx: RouteContext) {
  const session = await getSession();
  if (!isAdmin(session)) {
    return NextResponse.json({ error: "Admin access required" }, { status: 401 });
  }

  const { id } = await ctx.params;
  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const parsed = patchSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  if (Object.keys(parsed.data).length === 0) {
    return NextResponse.json({ error: "No fields to update" }, { status: 400 });
  }

  const svc = await createServiceRoleClient();

  // Load existing for diff in audit log.
  const { data: before } = await svc
    .from("clients")
    .select("id, company_name, status, seat_limit")
    .eq("id", id)
    .maybeSingle();

  if (!before) {
    return NextResponse.json({ error: "Organization not found" }, { status: 404 });
  }

  // If lowering seat limit, refuse if it would put the org below current usage.
  if (parsed.data.seat_limit !== undefined && parsed.data.seat_limit < before.seat_limit) {
    const { count: seatsUsed } = await svc
      .from("org_members")
      .select("id", { count: "exact", head: true })
      .eq("client_id", id)
      .is("deleted_at", null);
    if ((seatsUsed ?? 0) > parsed.data.seat_limit) {
      return NextResponse.json(
        {
          error: `Cannot lower seat limit below current usage (${seatsUsed} active members)`,
          seats_used: seatsUsed,
        },
        { status: 409 }
      );
    }
  }

  const { data: updated, error } = await svc
    .from("clients")
    .update({ ...parsed.data, updated_at: new Date().toISOString() })
    .eq("id", id)
    .select()
    .single();

  if (error || !updated) {
    return NextResponse.json({ error: "Failed to update organization" }, { status: 500 });
  }

  // Audit (best-effort).
  await svc.from("admin_audit_log").insert({
    actor_id: session.profileId,
    actor_role: session.role,
    action: "org.update",
    target_type: "organization",
    target_id: id,
    client_id: id,
    metadata: {
      before: {
        seat_limit: before.seat_limit,
        status: before.status,
        company_name: before.company_name,
      },
      after: parsed.data,
    },
    ip_address: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
    user_agent: request.headers.get("user-agent") ?? null,
  });

  return NextResponse.json({ organization: updated });
}
