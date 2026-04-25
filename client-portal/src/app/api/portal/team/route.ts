import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

/**
 * GET /api/portal/team
 * Returns the org's members + seat usage. Visible to both managers and
 * employees in the same org (read-only for employees; manager-only mutation
 * routes are below).
 */
export async function GET() {
  const session = await getSession();
  if (!session?.member) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const svc = await createServiceRoleClient();
  const { data: members, error } = await svc
    .from("org_members")
    .select("id, email, full_name, role, status, manager_id, invited_at, joined_at, last_login_at, created_at")
    .eq("client_id", session.member.clientId)
    .is("deleted_at", null)
    .order("role", { ascending: true })
    .order("created_at", { ascending: true });

  if (error) {
    return NextResponse.json({ error: "Failed to load team" }, { status: 500 });
  }

  return NextResponse.json({
    members: members ?? [],
    seat_limit: session.member.seatLimit,
    seats_used: members?.length ?? 0,
    company_name: session.member.companyName,
    can_manage: session.member.memberRole === "manager",
  });
}
