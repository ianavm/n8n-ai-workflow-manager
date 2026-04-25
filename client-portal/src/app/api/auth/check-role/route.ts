import { NextResponse } from "next/server";
import {
  createServerSupabaseClient,
  createServiceRoleClient,
} from "@/lib/supabase/server";

export async function GET() {
  try {
    const supabase = await createServerSupabaseClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();

    if (!user) {
      return NextResponse.json({ role: null, redirect: "/portal/login" });
    }

    const svc = await createServiceRoleClient();

    const { data: adminUser } = await svc
      .from("admin_users")
      .select("id, role")
      .eq("auth_user_id", user.id)
      .maybeSingle();

    if (adminUser) {
      return NextResponse.json({
        role: adminUser.role, // superior_admin | staff_admin
        redirect: "/admin",
      });
    }

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

    const { data: clientUser } = await svc
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle();

    if (clientUser) {
      const { data: member } = await svc
        .from("org_members")
        .select("role")
        .eq("auth_user_id", user.id)
        .is("deleted_at", null)
        .maybeSingle();

      const { data: faClient } = await svc
        .from("fa_clients")
        .select("id")
        .eq("portal_client_id", clientUser.id)
        .maybeSingle();

      return NextResponse.json({
        role: "client",
        memberRole: member?.role ?? null, // manager | employee | null
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
