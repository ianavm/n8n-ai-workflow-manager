import { NextResponse } from "next/server";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET() {
  const supabase = await createServerSupabaseClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { data: config } = await supabase
    .from("acct_config")
    .select("client_id")
    .limit(1)
    .maybeSingle();

  if (!config) return NextResponse.json({ data: null });

  const { data, error } = await supabase.rpc("acct_get_aged_receivables", {
    p_client_id: config.client_id,
  });

  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  return NextResponse.json({ data });
}
