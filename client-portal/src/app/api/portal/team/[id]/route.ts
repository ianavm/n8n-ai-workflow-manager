import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const patchSchema = z.object({
  role: z.enum(["manager", "employee"]).optional(),
  status: z.enum(["active", "suspended"]).optional(),
  full_name: z.string().trim().min(1).max(200).optional(),
});

interface RouteContext {
  params: Promise<{ id: string }>;
}

/** Manager-only. Promote/demote, suspend/reactivate, rename a member. */
export async function PATCH(request: NextRequest, ctx: RouteContext) {
  const session = await getSession();
  if (!session?.member) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (session.member.memberRole !== "manager") {
    return NextResponse.json({ error: "Manager-only" }, { status: 403 });
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

  const svc = await createServiceRoleClient();

  // Load target + assert same-org.
  const { data: target } = await svc
    .from("org_members")
    .select("id, client_id, role, status")
    .eq("id", id)
    .is("deleted_at", null)
    .maybeSingle();

  if (!target || target.client_id !== session.member.clientId) {
    return NextResponse.json({ error: "Member not found" }, { status: 404 });
  }

  // If demoting a manager, ensure another active manager remains.
  if (parsed.data.role === "employee" && target.role === "manager") {
    const { count: managerCount } = await svc
      .from("org_members")
      .select("id", { count: "exact", head: true })
      .eq("client_id", session.member.clientId)
      .eq("role", "manager")
      .is("deleted_at", null);
    if ((managerCount ?? 0) <= 1) {
      return NextResponse.json(
        { error: "Cannot demote the last remaining manager" },
        { status: 409 }
      );
    }
  }

  const updates: Record<string, unknown> = { updated_at: new Date().toISOString() };
  if (parsed.data.role !== undefined) {
    updates.role = parsed.data.role;
    // Promoted employees lose their manager_id pointer; demoted managers get
    // pointed at the caller as their new manager.
    updates.manager_id = parsed.data.role === "manager" ? null : session.member.memberId;
  }
  if (parsed.data.status !== undefined) updates.status = parsed.data.status;
  if (parsed.data.full_name !== undefined) updates.full_name = parsed.data.full_name;

  const { data: updated, error } = await svc
    .from("org_members")
    .update(updates)
    .eq("id", id)
    .select()
    .single();

  if (error || !updated) {
    return NextResponse.json({ error: "Failed to update member" }, { status: 500 });
  }

  return NextResponse.json({ member: updated });
}

/** Manager-only. Soft-delete a member (sets deleted_at). */
export async function DELETE(_req: NextRequest, ctx: RouteContext) {
  const session = await getSession();
  if (!session?.member) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (session.member.memberRole !== "manager") {
    return NextResponse.json({ error: "Manager-only" }, { status: 403 });
  }

  const { id } = await ctx.params;

  if (id === session.member.memberId) {
    return NextResponse.json({ error: "You cannot remove yourself" }, { status: 409 });
  }

  const svc = await createServiceRoleClient();

  const { data: target } = await svc
    .from("org_members")
    .select("id, client_id, role")
    .eq("id", id)
    .is("deleted_at", null)
    .maybeSingle();

  if (!target || target.client_id !== session.member.clientId) {
    return NextResponse.json({ error: "Member not found" }, { status: 404 });
  }

  // Don't strand the org without a manager.
  if (target.role === "manager") {
    const { count: managerCount } = await svc
      .from("org_members")
      .select("id", { count: "exact", head: true })
      .eq("client_id", session.member.clientId)
      .eq("role", "manager")
      .is("deleted_at", null);
    if ((managerCount ?? 0) <= 1) {
      return NextResponse.json(
        { error: "Cannot remove the last remaining manager" },
        { status: 409 }
      );
    }
  }

  const { error } = await svc
    .from("org_members")
    .update({
      deleted_at: new Date().toISOString(),
      status: "suspended",
      updated_at: new Date().toISOString(),
    })
    .eq("id", id);

  if (error) {
    return NextResponse.json({ error: "Failed to remove member" }, { status: 500 });
  }

  return NextResponse.json({ success: true });
}
