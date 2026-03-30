import { NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ role: null, redirect: "/portal/login" });
  }

  // Check admin_users first
  const { data: adminUser } = await supabase
    .from("admin_users")
    .select("id, role")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (adminUser) {
    return NextResponse.json({
      role: adminUser.role,
      redirect: "/admin",
    });
  }

  // Check fa_advisers
  const { data: adviser } = await supabase
    .from("fa_advisers")
    .select("id, role, firm_id")
    .eq("auth_user_id", user.id)
    .eq("active", true)
    .maybeSingle();

  if (adviser) {
    return NextResponse.json({
      role: adviser.role,
      redirect: "/admin/advisory/my-dashboard",
    });
  }

  // Check clients (portal users)
  const { data: clientUser } = await supabase
    .from("clients")
    .select("id")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (clientUser) {
    // Check if linked to FA client
    const { data: faClient } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("portal_client_id", clientUser.id)
      .maybeSingle();

    return NextResponse.json({
      role: "client",
      redirect: faClient ? "/portal/advisory/dashboard" : "/portal",
    });
  }

  return NextResponse.json({ role: null, redirect: "/portal/login" });
}
