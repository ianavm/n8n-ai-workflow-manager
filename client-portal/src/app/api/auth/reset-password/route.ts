import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { validatePassword } from "@/lib/validation";

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { client_id, new_password } = body;

  if (!client_id || !new_password) {
    return NextResponse.json(
      { error: "client_id and new_password are required" },
      { status: 400 }
    );
  }

  // Validate password strength
  const passwordError = validatePassword(new_password);
  if (passwordError) {
    return NextResponse.json({ error: passwordError }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  // Get client auth_user_id
  const { data: client } = await supabase
    .from("clients")
    .select("auth_user_id")
    .eq("id", client_id)
    .single();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  const { error } = await supabase.auth.admin.updateUserById(
    client.auth_user_id,
    { password: new_password }
  );

  if (error) {
    return NextResponse.json(
      { error: "Failed to reset password" },
      { status: 400 }
    );
  }

  await supabase.from("activity_log").insert({
    actor_type: "admin",
    actor_id: session.profileId,
    action: "password_reset",
    target_type: "client",
    target_id: client_id,
  });

  return NextResponse.json({ success: true });
}
