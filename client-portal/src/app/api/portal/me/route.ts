import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

/**
 * GET /api/portal/me
 * Returns the calling user's org_member context + seat usage. Used by
 * MemberProvider on the client.
 */
export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  // Admins have no org_member row.
  if (!session.member) {
    return NextResponse.json({ member: null, org: null });
  }

  const svc = await createServiceRoleClient();
  const { count } = await svc
    .from("org_members")
    .select("id", { count: "exact", head: true })
    .eq("client_id", session.member.clientId)
    .is("deleted_at", null);

  return NextResponse.json({
    member: {
      id: session.member.memberId,
      client_id: session.member.clientId,
      role: session.member.memberRole,
    },
    org: {
      seat_limit: session.member.seatLimit,
      total_members: count ?? 0,
      company_name: session.member.companyName,
    },
  });
}
