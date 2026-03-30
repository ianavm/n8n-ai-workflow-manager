import { NextResponse } from "next/server";
import {
  createServerSupabaseClient,
  createServiceRoleClient,
} from "@/lib/supabase/server";

export async function GET() {
  try {
    // Use the cookie-based client ONLY to verify the user's identity
    const supabase = await createServerSupabaseClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ role: null, redirect: "/portal/login" });
    }

    // Use service role client for all DB queries — bypasses RLS entirely
    const svc = await createServiceRoleClient();

    // Check admin_users first
    const { data: adminUser } = await svc
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
    const { data: adviser } = await svc
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
    const { data: clientUser } = await svc
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle();

    if (clientUser) {
      // Check if linked to FA client
      const { data: faClient } = await svc
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
  } catch {
    return NextResponse.json(
      { role: null, redirect: "/portal/login", error: "Role check failed" },
      { status: 500 }
    );
  }
}
