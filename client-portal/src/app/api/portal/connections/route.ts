import { NextResponse } from "next/server";
import { createServerSupabaseClient, createServiceRoleClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const svc = await createServiceRoleClient();

  const { data: client } = await svc
    .from("clients")
    .select("id")
    .eq("auth_user_id", user.id)
    .single();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Fetch existing connections
  const { data: connections } = await svc
    .from("oauth_connections")
    .select("id, provider, status, provider_account_name, connected_at, last_error, updated_at")
    .eq("client_id", client.id);

  return NextResponse.json({ connections: connections || [] });
}
