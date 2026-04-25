import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const EMAIL_REGEX = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const rawEmail: unknown = body?.email;

  if (typeof rawEmail !== "string" || rawEmail.length === 0) {
    return NextResponse.json({ error: "Email is required" }, { status: 400 });
  }
  const email = rawEmail.trim().toLowerCase();
  if (email.length > 255 || !EMAIL_REGEX.test(email)) {
    return NextResponse.json({ error: "Invalid email" }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  // Dedup against existing client + admin accounts to avoid issuing invites
  // to people who already have an account (which Supabase would silently ignore).
  const [{ data: existingClient }, { data: existingAdmin }] = await Promise.all([
    supabase.from("clients").select("id").eq("email", email).maybeSingle(),
    supabase.from("admin_users").select("id").eq("email", email).maybeSingle(),
  ]);
  if (existingClient || existingAdmin) {
    return NextResponse.json(
      { error: "An account with this email already exists" },
      { status: 409 }
    );
  }

  const { error } = await supabase.auth.admin.inviteUserByEmail(email, {
    redirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/portal/login`,
  });

  if (error) {
    console.error("[api/auth/invite] inviteUserByEmail failed:", error);
    return NextResponse.json(
      { error: "Failed to send invite" },
      { status: 400 }
    );
  }

  await supabase.from("activity_log").insert({
    actor_type: "admin",
    actor_id: session.profileId,
    action: "invite_sent",
    details: { email },
  });

  return NextResponse.json({ success: true });
}
