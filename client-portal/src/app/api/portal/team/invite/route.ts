import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const EMAIL_REGEX = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

const inviteSchema = z.object({
  email: z.string().trim().toLowerCase().max(255).regex(EMAIL_REGEX, "Invalid email"),
  full_name: z.string().trim().min(1).max(200),
  role: z.enum(["manager", "employee"]).default("employee"),
});

/**
 * POST /api/portal/team/invite
 * Manager-only. Invites a new employee (or co-manager) to the org. Enforces
 * the seat limit. Sends a Supabase invite email; the new member sets their
 * password on first login.
 */
export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session?.member) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }
  if (session.member.memberRole !== "manager") {
    return NextResponse.json({ error: "Only managers can invite team members" }, { status: 403 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = inviteSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const { email, full_name, role } = parsed.data;
  const svc = await createServiceRoleClient();

  // Seat limit gate — count active rows in this org.
  const { count: seatsUsed, error: countErr } = await svc
    .from("org_members")
    .select("id", { count: "exact", head: true })
    .eq("client_id", session.member.clientId)
    .is("deleted_at", null);

  if (countErr) {
    return NextResponse.json({ error: "Failed to check seat usage" }, { status: 500 });
  }

  if ((seatsUsed ?? 0) >= session.member.seatLimit) {
    return NextResponse.json(
      {
        error: "Seat limit reached",
        seats_used: seatsUsed,
        seat_limit: session.member.seatLimit,
      },
      { status: 409 }
    );
  }

  // Dedup against any existing identity.
  const [{ data: existingClient }, { data: existingAdmin }, { data: existingMember }] =
    await Promise.all([
      svc.from("clients").select("id").eq("email", email).maybeSingle(),
      svc.from("admin_users").select("id").eq("email", email).maybeSingle(),
      svc.from("org_members").select("id").eq("email", email).maybeSingle(),
    ]);

  if (existingClient || existingAdmin || existingMember) {
    return NextResponse.json(
      { error: "An account with this email already exists" },
      { status: 409 }
    );
  }

  // Send invite (Supabase emails the link).
  const { data: invited, error: inviteError } = await svc.auth.admin.inviteUserByEmail(email, {
    redirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/portal/login`,
    data: {
      full_name,
      org_member_role: role,
      invited_by_member_id: session.member.memberId,
    },
  });

  if (inviteError || !invited?.user) {
    return NextResponse.json(
      { error: "Failed to send invite", detail: inviteError?.message },
      { status: 400 }
    );
  }

  const authUserId = invited.user.id;

  // Insert org_members row. Employees get manager_id = caller; co-managers don't.
  const { data: member, error: memberError } = await svc
    .from("org_members")
    .insert({
      client_id: session.member.clientId,
      auth_user_id: authUserId,
      email,
      full_name,
      role,
      manager_id: role === "employee" ? session.member.memberId : null,
      status: "invited",
      invited_by: session.member.memberId,
      invited_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (memberError || !member) {
    await svc.auth.admin.deleteUser(authUserId);
    return NextResponse.json(
      { error: "Failed to create membership", detail: memberError?.message },
      { status: 500 }
    );
  }

  return NextResponse.json(
    {
      member,
      seats_used: (seatsUsed ?? 0) + 1,
      seat_limit: session.member.seatLimit,
    },
    { status: 201 }
  );
}
