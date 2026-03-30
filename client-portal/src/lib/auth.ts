import { createServerSupabaseClient } from "@/lib/supabase/server";

export type UserRole =
  | "owner"
  | "employee"
  | "client"
  | "adviser"
  | "compliance_officer";

export interface SessionUser {
  id: string;
  email: string;
  role: UserRole;
  profileId: string; // client.id or admin_users.id or fa_advisers.id
  fullName: string;
  firmId?: string; // fa_firms.id for advisory users
  adviserId?: string; // fa_advisers.id
  faClientId?: string; // fa_clients.id for portal clients linked to FA
}

export async function getSession(): Promise<SessionUser | null> {
  const supabase = await createServerSupabaseClient();

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  // Check if admin
  const { data: adminUser } = await supabase
    .from("admin_users")
    .select("id, email, full_name, role")
    .eq("auth_user_id", user.id)
    .single();

  if (adminUser) {
    return {
      id: user.id,
      email: adminUser.email,
      role: adminUser.role as UserRole,
      profileId: adminUser.id,
      fullName: adminUser.full_name,
    };
  }

  // Check if financial adviser
  const { data: adviser } = await supabase
    .from("fa_advisers")
    .select("id, email, full_name, role, firm_id")
    .eq("auth_user_id", user.id)
    .eq("active", true)
    .single();

  if (adviser) {
    return {
      id: user.id,
      email: adviser.email,
      role: adviser.role as UserRole,
      profileId: adviser.id,
      fullName: adviser.full_name,
      firmId: adviser.firm_id,
      adviserId: adviser.id,
    };
  }

  // Check if client
  const { data: clientUser } = await supabase
    .from("clients")
    .select("id, email, full_name")
    .eq("auth_user_id", user.id)
    .single();

  if (clientUser) {
    // Check if linked to a financial advisory client
    const { data: faClient } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", clientUser.id)
      .single();

    return {
      id: user.id,
      email: clientUser.email,
      role: "client",
      profileId: clientUser.id,
      fullName: clientUser.full_name,
      firmId: faClient?.firm_id,
      faClientId: faClient?.id,
    };
  }

  return null;
}

export async function requireAdmin(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || (session.role !== "owner" && session.role !== "employee")) {
    throw new Error("Unauthorized: Admin access required");
  }
  return session;
}

export async function requireOwner(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || session.role !== "owner") {
    throw new Error("Unauthorized: Owner access required");
  }
  return session;
}

export async function requireClient(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || session.role !== "client") {
    throw new Error("Unauthorized: Client access required");
  }
  return session;
}

export async function requireAdviser(): Promise<SessionUser> {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "owner"].includes(session.role)
  ) {
    throw new Error("Unauthorized: Adviser access required");
  }
  return session;
}

export async function requireComplianceOfficer(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || !["compliance_officer", "owner"].includes(session.role)) {
    throw new Error("Unauthorized: Compliance access required");
  }
  return session;
}
