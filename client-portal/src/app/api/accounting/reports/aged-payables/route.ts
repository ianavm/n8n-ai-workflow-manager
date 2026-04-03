import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const url = new URL(req.url);
  const requestedClientId = url.searchParams.get("client_id");

  let configQuery = supabase.from("acct_config").select("client_id");
  if (requestedClientId) {
    configQuery = configQuery.eq("client_id", requestedClientId);
  } else {
    configQuery = configQuery.order("created_at", { ascending: true }).limit(1);
  }
  const { data: config } = await configQuery.maybeSingle();

  if (!config) return NextResponse.json({ data: null });

  const { data, error } = await supabase.rpc("acct_get_aged_payables", {
    p_client_id: config.client_id,
  });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ data });
}
