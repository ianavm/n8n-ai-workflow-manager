import { createServerSupabaseClient, createServiceRoleClient } from "@/lib/supabase/server";

export type UserRole =
  | "superior_admin"     // Ian — account lifecycle only (POPIA: no business data)
  | "staff_admin"        // AVM delivery team — full service-delivery access
  | "client"             // portal user — wraps an org_members row (manager | employee)
  | "adviser"            // fa_advisers
  | "compliance_officer" // fa_advisers
  | "office_manager"     // fa_advisers
  | "super_admin";       // fa_advisers top role (distinct from admin_users)

export type MemberRole = "manager" | "employee";

export interface MemberContext {
  memberId: string;
  clientId: string;
  memberRole: MemberRole;
  managerId: string | null;
  seatLimit: number;
  companyName: string;
}

export interface SessionUser {
  id: string;
  email: string;
  role: UserRole;
  profileId: string;
  fullName: string;
  firmId?: string;
  adviserId?: string;
  faClientId?: string;
  member?: MemberContext;
}

export async function getSession(): Promise<SessionUser | null> {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const svc = await createServiceRoleClient();

  const { data: adminUser } = await svc
    .from("admin_users")
    .select("id, email, full_name, role")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (adminUser) {
    const { data: adviserData } = await svc
      .from("fa_advisers")
      .select("id, firm_id")
      .eq("auth_user_id", user.id)
      .eq("active", true)
      .maybeSingle();

    return {
      id: user.id,
      email: adminUser.email,
      role: adminUser.role as UserRole,
      profileId: adminUser.id,
      fullName: adminUser.full_name,
      firmId: adviserData?.firm_id,
      adviserId: adviserData?.id,
    };
  }

  const { data: adviser } = await svc
    .from("fa_advisers")
    .select("id, email, full_name, role, firm_id")
    .eq("auth_user_id", user.id)
    .eq("active", true)
    .maybeSingle();

  if (adviser) {
    const role = adviser.role === "admin" ? "super_admin" : adviser.role;
    return {
      id: user.id,
      email: adviser.email,
      role: role as UserRole,
      profileId: adviser.id,
      fullName: adviser.full_name,
      firmId: adviser.firm_id,
      adviserId: adviser.id,
    };
  }

  // Resolve the org + member context. Two paths:
  //   (a) Manager auth user — owns a `clients` row (auth_user_id matches).
  //   (b) Invited employee — has an `org_members` row but the parent
  //       `clients.auth_user_id` belongs to the original manager.
  // Try (a) first, fall back to (b).
  let clientUser:
    | {
        id: string;
        email: string;
        full_name: string;
        company_name: string | null;
        seat_limit: number | null;
      }
    | null = null;

  const { data: clientByAuth } = await svc
    .from("clients")
    .select("id, email, full_name, company_name, seat_limit")
    .eq("auth_user_id", user.id)
    .maybeSingle();
  clientUser = clientByAuth ?? null;

  const { data: member } = await svc
    .from("org_members")
    .select("id, client_id, role, manager_id, status, email, full_name")
    .eq("auth_user_id", user.id)
    .is("deleted_at", null)
    .maybeSingle();

  if (!clientUser && member) {
    const { data: parentClient } = await svc
      .from("clients")
      .select("id, email, full_name, company_name, seat_limit")
      .eq("id", member.client_id)
      .maybeSingle();
    if (parentClient) {
      // Employee identity comes from the org_members row, not the parent
      // clients row (which belongs to the manager).
      clientUser = {
        id: parentClient.id,
        email: member.email,
        full_name: member.full_name ?? "",
        company_name: parentClient.company_name,
        seat_limit: parentClient.seat_limit,
      };
    }
  }

  if (clientUser) {
    const { data: faClient } = await svc
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", clientUser.id)
      .maybeSingle();

    const memberCtx: MemberContext | undefined = member
      ? {
          memberId: member.id,
          clientId: member.client_id,
          memberRole: member.role as MemberRole,
          managerId: member.manager_id,
          seatLimit: clientUser.seat_limit ?? 5,
          companyName: clientUser.company_name ?? "",
        }
      : undefined;

    return {
      id: user.id,
      email: clientUser.email,
      role: "client",
      profileId: clientUser.id,
      fullName: clientUser.full_name,
      firmId: faClient?.firm_id,
      faClientId: faClient?.id,
      member: memberCtx,
    };
  }

  return null;
}

// ---------- Role predicates ----------

export function isAdmin(session: SessionUser | null): session is SessionUser {
  return !!session && (session.role === "superior_admin" || session.role === "staff_admin");
}

export function isSuperiorAdmin(session: SessionUser | null): session is SessionUser {
  return !!session && session.role === "superior_admin";
}

export function isStaffAdmin(session: SessionUser | null): session is SessionUser {
  return !!session && session.role === "staff_admin";
}

export function isManager(session: SessionUser | null): boolean {
  return !!session && session.role === "client" && session.member?.memberRole === "manager";
}

export function isEmployee(session: SessionUser | null): boolean {
  return !!session && session.role === "client" && session.member?.memberRole === "employee";
}

/**
 * POPIA gate. superior_admin can see org metadata (seat counts, membership
 * lifecycle) but MUST NOT see client business data (leads, documents,
 * communications, per-event telemetry). Check this before running queries
 * that touch client-of-client PII.
 */
export function canViewBusinessData(session: SessionUser | null): boolean {
  if (!session) return false;
  return session.role !== "superior_admin";
}

// ---------- Required-role helpers ----------

export async function requireAdmin(): Promise<SessionUser> {
  const session = await getSession();
  if (!isAdmin(session)) throw new Error("Unauthorized: Admin access required");
  return session;
}

export async function requireSuperiorAdmin(): Promise<SessionUser> {
  const session = await getSession();
  if (!isSuperiorAdmin(session)) throw new Error("Unauthorized: Superior admin access required");
  return session;
}

export async function requireStaffAdmin(): Promise<SessionUser> {
  const session = await getSession();
  if (!isStaffAdmin(session)) throw new Error("Unauthorized: Staff admin access required");
  return session;
}

/** Legacy alias preserved for callsites that meant "top-tier admin". Superior admin only. */
export async function requireOwner(): Promise<SessionUser> {
  return requireSuperiorAdmin();
}

export async function requireClient(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || session.role !== "client") {
    throw new Error("Unauthorized: Client access required");
  }
  return session;
}

export async function requireManager(): Promise<SessionUser> {
  const session = await getSession();
  if (!isManager(session)) throw new Error("Unauthorized: Manager access required");
  return session!;
}

export async function requireAdviser(): Promise<SessionUser> {
  const session = await getSession();
  if (
    !session ||
    !["adviser", "compliance_officer", "office_manager", "super_admin", "staff_admin"].includes(
      session.role
    )
  ) {
    throw new Error("Unauthorized: Adviser access required");
  }
  return session;
}

export async function requireComplianceOfficer(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || !["compliance_officer", "staff_admin"].includes(session.role)) {
    throw new Error("Unauthorized: Compliance access required");
  }
  return session;
}

export async function requireSuperAdmin(): Promise<SessionUser> {
  const session = await getSession();
  if (!session || !["super_admin", "staff_admin"].includes(session.role)) {
    throw new Error("Unauthorized: Super admin access required");
  }
  return session;
}

export async function requireOfficeManager(): Promise<SessionUser> {
  const session = await getSession();
  if (
    !session ||
    !["office_manager", "super_admin", "staff_admin"].includes(session.role)
  ) {
    throw new Error("Unauthorized: Office manager access required");
  }
  return session;
}

/** Single-shot session + member context. */
export async function getMemberContext(): Promise<{
  session: SessionUser | null;
  member: MemberContext | null;
}> {
  const session = await getSession();
  return { session, member: session?.member ?? null };
}
