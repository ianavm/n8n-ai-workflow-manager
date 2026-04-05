import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient, createServiceRoleClient } from "@/lib/supabase/server";

export async function POST(request: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { step_data } = body;

  const svc = await createServiceRoleClient();

  // Find client
  const { data: client } = await svc
    .from("clients")
    .select("id, email, full_name, onboarding_completed_at")
    .eq("auth_user_id", user.id)
    .single();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Idempotency guard — don't re-process if already completed (HIGH-2 fix)
  if (client.onboarding_completed_at) {
    return NextResponse.json({ success: true });
  }

  const now = new Date().toISOString();

  // Update onboarding_progress as completed
  await svc
    .from("onboarding_progress")
    .update({
      completed_at: now,
      current_step: 5,
      ...(step_data ? { step_data } : {}),
    })
    .eq("client_id", client.id);

  // Update client profile with progressive profiling data
  const profileData = step_data?.business_profile;
  const clientUpdate: Record<string, unknown> = {
    onboarding_completed_at: now,
    profile_completed: true,
  };

  if (profileData) {
    if (profileData.industry) clientUpdate.industry = profileData.industry;
    if (profileData.company_size) clientUpdate.company_size = profileData.company_size;
    if (profileData.primary_need) clientUpdate.primary_need = profileData.primary_need;
    if (profileData.phone_number) clientUpdate.phone_number = profileData.phone_number;
    if (profileData.company_name) clientUpdate.company_name = profileData.company_name;
  }

  await svc
    .from("clients")
    .update(clientUpdate)
    .eq("id", client.id);

  // Grant profile_completed achievement
  if (profileData?.industry && profileData?.company_size && profileData?.primary_need) {
    await svc.from("client_achievements").upsert(
      { client_id: client.id, achievement_key: "profile_completed" },
      { onConflict: "client_id,achievement_key" }
    );
  }

  // Log activity
  await svc.from("activity_log").insert({
    actor_type: "client",
    actor_id: client.id,
    action: "onboarding_completed",
    target_type: "client",
    target_id: client.id,
    details: {
      selected_tools: step_data?.connect_tools?.selected_tools || [],
      selected_template: step_data?.choose_automation?.selected_template || null,
      industry: profileData?.industry || null,
      primary_need: profileData?.primary_need || null,
    },
    ip_address:
      request.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
      "unknown",
  });

  return NextResponse.json({ success: true });
}
