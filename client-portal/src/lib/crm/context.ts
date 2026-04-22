import { createServerSupabaseClient } from "@/lib/supabase/server";

export interface CrmViewerContext {
  userId: string;
  isAdmin: boolean;
  clientId: string | null;  // null when viewer is an AVM admin without an impersonated client
  viewAsClientId: string | null;  // admins can override via ?client= query
}

export async function getCrmViewerContext(
  viewAsClientId?: string | null,
): Promise<CrmViewerContext | null> {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) return null;

  const [{ data: admin }, { data: client }] = await Promise.all([
    supabase
      .from("admin_users")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle(),
    supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .maybeSingle(),
  ]);

  const isAdmin = Boolean(admin);

  return {
    userId: user.id,
    isAdmin,
    clientId: client?.id ?? null,
    viewAsClientId: isAdmin && viewAsClientId ? viewAsClientId : null,
  };
}

/**
 * Returns the client_id that CRM queries should be scoped to.
 * - Admin + ?client=<id> → that id
 * - Admin + no override  → null (means "all clients", only allowed in admin endpoints)
 * - Client user          → their own client_id
 */
export function resolveScopedClientId(ctx: CrmViewerContext): string | null {
  if (ctx.isAdmin) return ctx.viewAsClientId;
  return ctx.clientId;
}
