import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { getSession, isAdmin } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const EMAIL_REGEX = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

const createOrgSchema = z.object({
  company_name: z.string().trim().min(1, "Company name is required").max(200),
  manager_email: z.string().trim().toLowerCase().max(255).regex(EMAIL_REGEX, "Invalid email"),
  manager_full_name: z.string().trim().min(1, "Manager name is required").max(200),
  seat_limit: z.number().int().min(1).max(500).default(5),
});

/**
 * POST /api/admin/organizations
 * One-click org provisioning for admins.
 *   1. Create auth user (invite email sent automatically)
 *   2. Insert clients row (the organization)
 *   3. Insert org_members row (role='manager', status='invited')
 *   4. Append admin_audit_log entry
 * Rolls back prior steps on failure.
 */
export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!isAdmin(session)) {
    return NextResponse.json({ error: "Admin access required" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const parsed = createOrgSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Validation failed", details: parsed.error.flatten().fieldErrors },
      { status: 400 }
    );
  }

  const { company_name, manager_email, manager_full_name, seat_limit } = parsed.data;
  const supabase = await createServiceRoleClient();

  // Dedup guard — stop if the email already exists anywhere.
  const [{ data: existingClient }, { data: existingAdmin }, { data: existingMember }] =
    await Promise.all([
      supabase.from("clients").select("id").eq("email", manager_email).maybeSingle(),
      supabase.from("admin_users").select("id").eq("email", manager_email).maybeSingle(),
      supabase.from("org_members").select("id").eq("email", manager_email).maybeSingle(),
    ]);

  if (existingClient || existingAdmin || existingMember) {
    return NextResponse.json(
      { error: "An account with this email already exists" },
      { status: 409 }
    );
  }

  // 1. Invite auth user (Supabase sends the email).
  const { data: invited, error: inviteError } = await supabase.auth.admin.inviteUserByEmail(
    manager_email,
    {
      redirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/portal/login`,
      data: { full_name: manager_full_name, company_name },
    }
  );

  if (inviteError || !invited?.user) {
    return NextResponse.json(
      { error: "Failed to send invite", detail: inviteError?.message },
      { status: 400 }
    );
  }

  const authUserId = invited.user.id;

  // 2. Insert org (clients row).
  const { data: client, error: clientError } = await supabase
    .from("clients")
    .insert({
      auth_user_id: authUserId,
      email: manager_email,
      full_name: manager_full_name,
      company_name,
      seat_limit,
      status: "active",
      created_by: session.profileId,
    })
    .select()
    .single();

  if (clientError || !client) {
    await supabase.auth.admin.deleteUser(authUserId);
    return NextResponse.json(
      { error: "Failed to create organization", detail: clientError?.message },
      { status: 500 }
    );
  }

  // 3. Insert manager org_member row.
  const { data: member, error: memberError } = await supabase
    .from("org_members")
    .insert({
      client_id: client.id,
      auth_user_id: authUserId,
      email: manager_email,
      full_name: manager_full_name,
      role: "manager",
      status: "invited",
      invited_at: new Date().toISOString(),
    })
    .select()
    .single();

  if (memberError || !member) {
    await supabase.from("clients").delete().eq("id", client.id);
    await supabase.auth.admin.deleteUser(authUserId);
    return NextResponse.json(
      { error: "Failed to create manager membership", detail: memberError?.message },
      { status: 500 }
    );
  }

  // 4. Audit log (best-effort — don't fail the request if this table isn't present).
  await supabase.from("admin_audit_log").insert({
    actor_id: session.profileId,
    actor_role: session.role,
    action: "org.create",
    target_type: "organization",
    target_id: client.id,
    client_id: client.id,
    metadata: {
      company_name,
      manager_email,
      manager_full_name,
      seat_limit,
      manager_member_id: member.id,
    },
    ip_address: request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ?? null,
    user_agent: request.headers.get("user-agent") ?? null,
  });

  return NextResponse.json(
    {
      client_id: client.id,
      manager_member_id: member.id,
      company_name,
      manager_email,
      status: "active",
      invite_sent: true,
    },
    { status: 201 }
  );
}
