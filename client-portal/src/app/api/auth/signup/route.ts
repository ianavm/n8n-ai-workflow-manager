import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { validatePassword, extractClientIp } from "@/lib/validation";
import { PUBLIC_SIGNUPS_ENABLED } from "@/lib/signup-config";

// Trial duration in days
const TRIAL_DAYS = 30;

type SignupMethod = "email" | "magic_link" | "google_sso";

export async function POST(request: NextRequest) {
  if (!PUBLIC_SIGNUPS_ENABLED) {
    return NextResponse.json(
      {
        error:
          "Self-service signups are closed. Please contact sales at ian@anyvisionmedia.com to request access.",
      },
      { status: 403 }
    );
  }

  const body = await request.json();
  const {
    email,
    password,
    full_name,
    company_name,
    signup_method = "magic_link",
    // Legacy fields for backwards compatibility
    first_name,
    last_name,
  } = body;

  // Build full name from either new or legacy format
  const resolvedName =
    full_name?.trim() ||
    (first_name && last_name
      ? `${first_name.trim()} ${last_name.trim()}`
      : null);

  // Validate required fields
  if (!email || !resolvedName) {
    return NextResponse.json(
      { error: "Email and full name are required" },
      { status: 400 }
    );
  }

  // Validate field lengths
  if (resolvedName.length < 2 || resolvedName.length > 200) {
    return NextResponse.json(
      { error: "Name must be 2-200 characters" },
      { status: 400 }
    );
  }
  // Block obviously bot-generated names (must contain at least one letter
  // and must not be a gibberish block of random consonants — reject strings
  // with >8 consecutive letters and no vowels or spaces).
  if (!/[a-zA-Z]/.test(resolvedName)) {
    return NextResponse.json(
      { error: "Name must contain at least one letter" },
      { status: 400 }
    );
  }
  if (/[a-zA-Z]{9,}/.test(resolvedName) && !/[aeiouAEIOU\s]/.test(resolvedName)) {
    return NextResponse.json(
      { error: "Please enter a valid name" },
      { status: 400 }
    );
  }
  if (company_name && company_name.trim().length > 200) {
    return NextResponse.json(
      { error: "Company name is too long (max 200 characters)" },
      { status: 400 }
    );
  }

  // Validate email format (stricter than before — rejects double @ and
  // missing TLD cases)
  const emailRegex = /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/;
  if (!emailRegex.test(email) || email.length > 255) {
    return NextResponse.json(
      { error: "Please enter a valid email address" },
      { status: 400 }
    );
  }

  // Only validate password if provided (password-based signup)
  const isPasswordSignup = !!password;
  if (isPasswordSignup) {
    const passwordError = validatePassword(password);
    if (passwordError) {
      return NextResponse.json({ error: passwordError }, { status: 400 });
    }
  }

  const supabase = await createServiceRoleClient();
  const appUrl =
    process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

  // Create auth user
  const createUserPayload: {
    email: string;
    password?: string;
    email_confirm: boolean;
    user_metadata: { full_name: string; company_name: string | null };
  } = {
    email,
    email_confirm: true,
    user_metadata: {
      full_name: resolvedName,
      company_name: company_name?.trim() || null,
    },
  };

  if (isPasswordSignup) {
    createUserPayload.password = password;
  }

  const { data: authData, error: authError } =
    await supabase.auth.admin.createUser(createUserPayload);

  if (authError) {
    if (
      authError.message?.includes("already been registered") ||
      authError.message?.includes("already exists")
    ) {
      return NextResponse.json(
        {
          error:
            "An account with this email already exists. Try signing in or resetting your password.",
        },
        { status: 409 }
      );
    }
    return NextResponse.json(
      { error: "Failed to create account. Please try again." },
      { status: 400 }
    );
  }

  const authUserId = authData.user.id;

  // Determine signup method
  const method: SignupMethod = isPasswordSignup
    ? "email"
    : (signup_method as SignupMethod) || "magic_link";

  // Create client record
  const { data: client, error: clientError } = await supabase
    .from("clients")
    .insert({
      auth_user_id: authUserId,
      email: email.toLowerCase().trim(),
      full_name: resolvedName,
      company_name: company_name?.trim() || null,
      email_verified: true,
      signup_method: method,
      created_by: null,
    })
    .select()
    .single();

  if (clientError) {
    // Rollback: delete the auth user
    await supabase.auth.admin.deleteUser(authUserId);
    return NextResponse.json(
      { error: "Failed to create client profile. Please try again." },
      { status: 500 }
    );
  }

  // Auto-create 30-day trial subscription on Starter plan
  const { data: starterPlan } = await supabase
    .from("plans")
    .select("id")
    .eq("slug", "starter")
    .single();

  if (starterPlan) {
    const now = new Date();
    const trialEnd = new Date(
      now.getTime() + TRIAL_DAYS * 24 * 60 * 60 * 1000
    );

    await supabase.from("subscriptions").insert({
      client_id: client.id,
      plan_id: starterPlan.id,
      status: "trialing",
      billing_interval: "monthly",
      trial_start: now.toISOString(),
      trial_end: trialEnd.toISOString(),
      current_period_start: now.toISOString(),
      current_period_end: trialEnd.toISOString(),
    });
  }

  // For magic link signup: use admin.generateLink to get the action link,
  // then send it via Supabase's built-in invite flow.
  // admin.inviteUserByEmail sends the email through Supabase's email provider.
  if (!isPasswordSignup) {
    // inviteUserByEmail sends a "You've been invited" email with a magic link.
    // Since user already exists (created above), this generates and SENDS the link.
    await supabase.auth.admin.inviteUserByEmail(email, {
      redirectTo: `${appUrl}/portal/auth/callback?onboarding=true`,
    });
  }

  // Grant account_created achievement (ignore errors — non-critical)
  await supabase.from("client_achievements").upsert(
    { client_id: client.id, achievement_key: "account_created" },
    { onConflict: "client_id,achievement_key" }
  );

  // Log activity
  const ip = extractClientIp(request);
  await supabase.from("activity_log").insert({
    actor_type: "system",
    actor_id: client.id,
    action: "client_self_signup",
    target_type: "client",
    target_id: client.id,
    details: {
      email,
      full_name: resolvedName,
      trial_days: TRIAL_DAYS,
      signup_method: method,
    },
    ip_address: ip,
  });

  return NextResponse.json({ success: true }, { status: 201 });
}
