import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function GET() {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServerSupabaseClient();

  const { data: client, error } = await supabase
    .from("clients")
    .select("last_login_at, last_login_ip, last_login_device, created_at")
    .eq("id", session.profileId)
    .single();

  if (error || !client) {
    return NextResponse.json(
      { error: "Failed to fetch security info" },
      { status: 500 }
    );
  }

  return NextResponse.json(client);
}
