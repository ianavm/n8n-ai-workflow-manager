import { NextRequest, NextResponse } from "next/server";
import { createServerSupabaseClient, createServiceRoleClient } from "@/lib/supabase/server";

// GET: Return current onboarding progress (creates record if missing)
export async function GET() {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const svc = await createServiceRoleClient();

  // Find client
  const { data: client } = await svc
    .from("clients")
    .select("id")
    .eq("auth_user_id", user.id)
    .single();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Get or create onboarding progress
  const { data: progress } = await svc
    .from("onboarding_progress")
    .select("*")
    .eq("client_id", client.id)
    .maybeSingle();

  if (progress) {
    return NextResponse.json({ progress });
  }

  // Create new progress record
  const { data: newProgress, error: createError } = await svc
    .from("onboarding_progress")
    .insert({
      client_id: client.id,
      current_step: 1,
      step_data: {},
      completed_steps: [],
      skipped_steps: [],
    })
    .select()
    .single();

  if (createError) {
    return NextResponse.json(
      { error: "Failed to initialize onboarding" },
      { status: 500 }
    );
  }

  return NextResponse.json({ progress: newProgress });
}

// PATCH: Update onboarding progress
export async function PATCH(request: NextRequest) {
  const supabase = await createServerSupabaseClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await request.json();
  const { current_step, step_data, completed_steps, skipped_steps } = body;

  const svc = await createServiceRoleClient();

  // Find client
  const { data: client } = await svc
    .from("clients")
    .select("id")
    .eq("auth_user_id", user.id)
    .single();

  if (!client) {
    return NextResponse.json({ error: "Client not found" }, { status: 404 });
  }

  // Validate input (MEDIUM-1 fix)
  if (current_step !== undefined && (typeof current_step !== "number" || current_step < 1 || current_step > 5)) {
    return NextResponse.json({ error: "Invalid current_step" }, { status: 400 });
  }
  if (completed_steps !== undefined && !Array.isArray(completed_steps)) {
    return NextResponse.json({ error: "Invalid completed_steps" }, { status: 400 });
  }
  if (skipped_steps !== undefined && !Array.isArray(skipped_steps)) {
    return NextResponse.json({ error: "Invalid skipped_steps" }, { status: 400 });
  }

  // Atomic upsert — prevents race condition on concurrent saves (CRITICAL-2 fix)
  const { error: upsertError } = await svc
    .from("onboarding_progress")
    .upsert(
      {
        client_id: client.id,
        current_step: current_step ?? 1,
        step_data: step_data ?? {},
        completed_steps: completed_steps ?? [],
        skipped_steps: skipped_steps ?? [],
      },
      { onConflict: "client_id" }
    );

  if (upsertError) {
    return NextResponse.json(
      { error: "Failed to save progress" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
