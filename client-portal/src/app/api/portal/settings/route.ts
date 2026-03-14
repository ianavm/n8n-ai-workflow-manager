import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServerSupabaseClient } from "@/lib/supabase/server";

export async function PATCH(request: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { full_name, company_name, phone_number } = body;

  if (!full_name?.trim()) {
    return NextResponse.json(
      { error: "Full name is required" },
      { status: 400 }
    );
  }

  const supabase = await createServerSupabaseClient();

  const { error } = await supabase
    .from("clients")
    .update({
      full_name: full_name.trim(),
      company_name: company_name?.trim() || null,
      phone_number: phone_number?.trim() || null,
      updated_at: new Date().toISOString(),
    })
    .eq("id", session.profileId);

  if (error) {
    return NextResponse.json(
      { error: "Failed to update profile" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}

export async function GET() {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServerSupabaseClient();

  const { data: client, error } = await supabase
    .from("clients")
    .select("full_name, email, company_name, phone_number, email_verified, created_at")
    .eq("id", session.profileId)
    .single();

  if (error || !client) {
    return NextResponse.json(
      { error: "Failed to fetch profile" },
      { status: 500 }
    );
  }

  return NextResponse.json(client);
}
