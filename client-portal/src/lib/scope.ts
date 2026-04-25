import { canViewBusinessData, type SessionUser } from "@/lib/auth";

/** Thrown when a superior_admin attempts to read business data. */
export class POPIAViolationError extends Error {
  constructor(detail?: string) {
    super(detail ?? "Superior admin is not permitted to read business data");
    this.name = "POPIAViolationError";
  }
}

interface QueryLike {
  eq: (column: string, value: unknown) => QueryLike;
}

interface ScopeOptions {
  /**
   * Set false for tables that don't have an `org_member_id` column
   * (e.g. `clients`, `mkt_config`, `client_health_scores`). Defaults to
   * true since most fact tables added the column in migration 033.
   */
  tableHasMemberCol?: boolean;
  /**
   * Custom column name for the org foreign key when the table doesn't use
   * `client_id`. Defaults to "client_id".
   */
  clientCol?: string;
  /** Custom column name for the member foreign key. Defaults to "org_member_id". */
  memberCol?: string;
}

/**
 * Apply org / org_member scoping to a Supabase query based on the session.
 *
 *   superior_admin → throws POPIAViolationError
 *   staff_admin    → returns query unchanged (admin endpoints handle their own scoping)
 *   client/manager → filter by client_id only
 *   client/employee → filter by client_id AND org_member_id
 *
 * Usage:
 *   const { data } = await scopeQuery(
 *     supabase.from("stat_events").select("*"),
 *     session,
 *   );
 */
export function scopeQuery<Q extends QueryLike>(
  query: Q,
  session: SessionUser | null,
  opts: ScopeOptions = {},
): Q {
  if (!session) throw new Error("Unauthorized: no session");
  if (!canViewBusinessData(session)) throw new POPIAViolationError();

  // staff_admin sees everything in admin endpoints; portal endpoints reject
  // admins with a 401 before reaching here.
  if (session.role === "staff_admin") return query;

  if (session.role !== "client" || !session.member) {
    throw new Error("Forbidden: portal session required");
  }

  const clientCol = opts.clientCol ?? "client_id";
  const memberCol = opts.memberCol ?? "org_member_id";
  const tableHasMemberCol = opts.tableHasMemberCol ?? true;

  let scoped = query.eq(clientCol, session.member.clientId) as Q;
  if (tableHasMemberCol && session.member.memberRole === "employee") {
    scoped = scoped.eq(memberCol, session.member.memberId) as Q;
  }
  return scoped;
}

/** Convenience: just the IDs you need to inject into bespoke queries / RPC args. */
export function scopeIds(session: SessionUser | null): {
  clientId: string;
  orgMemberId: string | null;
} {
  if (!session) throw new Error("Unauthorized");
  if (!canViewBusinessData(session)) throw new POPIAViolationError();
  if (session.role !== "client" || !session.member) {
    throw new Error("Forbidden: portal session required");
  }
  return {
    clientId: session.member.clientId,
    orgMemberId:
      session.member.memberRole === "employee" ? session.member.memberId : null,
  };
}
