import { createServerSupabaseClient, createServiceRoleClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";

const TRIAL_DAYS = 30;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const code = searchParams.get("code");

  if (!code) {
    return NextResponse.redirect(new URL("/portal/login", request.url));
  }

  const supabase = await createServerSupabaseClient();
  const { error } = await supabase.auth.exchangeCodeForSession(code);

  if (error) {
    return NextResponse.redirect(new URL("/portal/login", request.url));
  }

  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.redirect(new URL("/portal/login", request.url));
  }

  // Use service role to check/create client record (bypasses RLS)
  const svc = await createServiceRoleClient();

  // Check if client record exists
  const { data: existingClient } = await svc
    .from("clients")
    .select("id, onboarding_completed_at")
    .eq("auth_user_id", user.id)
    .maybeSingle();

  if (existingClient) {
    // Existing user — mark email as verified
    await svc
      .from("clients")
      .update({ email_verified: true })
      .eq("id", existingClient.id);

    // Redirect based on onboarding status
    if (!existingClient.onboarding_completed_at) {
      return NextResponse.redirect(new URL("/portal/onboarding", request.url));
    }
    return NextResponse.redirect(new URL("/portal", request.url));
  }

  // Check if a client with this email already exists (account linking for Google SSO)
  // This handles: user signed up via email, then later clicks "Continue with Google"
  const userEmail = (user.email || "").toLowerCase().trim();
  const { data: emailClient } = await svc
    .from("clients")
    .select("id, onboarding_completed_at")
    .eq("email", userEmail)
    .maybeSingle();

  if (emailClient) {
    // Link the Google auth user to the existing client record
    await svc
      .from("clients")
      .update({ auth_user_id: user.id, email_verified: true, signup_method: "google_sso" })
      .eq("id", emailClient.id);

    if (!emailClient.onboarding_completed_at) {
      return NextResponse.redirect(new URL("/portal/onboarding", request.url));
    }
    return NextResponse.redirect(new URL("/portal", request.url));
  }

  // Truly new user (Google SSO) — create client record from Google metadata
  const fullName =
    user.user_metadata?.full_name ||
    user.user_metadata?.name ||
    userEmail.split("@")[0] ||
    "New User";

  const { data: newClient, error: clientError } = await svc
    .from("clients")
    .insert({
      auth_user_id: user.id,
      email: userEmail,
      full_name: fullName,
      company_name: null,
      email_verified: true,
      signup_method: "google_sso",
      created_by: null,
    })
    .select()
    .single();

  if (clientError) {
    return NextResponse.redirect(
      new URL("/portal/login?error=signup_failed", request.url)
    );
  }

  // Auto-create 30-day trial subscription on Starter plan
  const { data: starterPlan } = await svc
    .from("plans")
    .select("id")
    .eq("slug", "starter")
    .single();

  if (starterPlan) {
    const now = new Date();
    const trialEnd = new Date(
      now.getTime() + TRIAL_DAYS * 24 * 60 * 60 * 1000
    );

    await svc.from("subscriptions").insert({
      client_id: newClient.id,
      plan_id: starterPlan.id,
      status: "trialing",
      billing_interval: "monthly",
      trial_start: now.toISOString(),
      trial_end: trialEnd.toISOString(),
      current_period_start: now.toISOString(),
      current_period_end: trialEnd.toISOString(),
    });
  }

  // Grant account_created achievement
  await svc.from("client_achievements").upsert(
    { client_id: newClient.id, achievement_key: "account_created" },
    { onConflict: "client_id,achievement_key" }
  );

  // Log activity
  await svc.from("activity_log").insert({
    actor_type: "system",
    actor_id: newClient.id,
    action: "client_self_signup",
    target_type: "client",
    target_id: newClient.id,
    details: {
      email: user.email,
      full_name: fullName,
      trial_days: TRIAL_DAYS,
      signup_method: "google_sso",
    },
    ip_address:
      request.headers.get("x-forwarded-for")?.split(",")[0].trim() ||
      "unknown",
  });

  // New users always go to onboarding
  return NextResponse.redirect(new URL("/portal/onboarding", request.url));
}
