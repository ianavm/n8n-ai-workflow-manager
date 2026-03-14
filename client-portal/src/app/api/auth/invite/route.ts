import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { email } = body;

  if (!email) {
    return NextResponse.json({ error: "Email is required" }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  const { error } = await supabase.auth.admin.inviteUserByEmail(email, {
    redirectTo: `${process.env.NEXT_PUBLIC_APP_URL}/portal/login`,
  });

  if (error) {
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
