import { NextRequest, NextResponse } from "next/server";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { validatePassword, extractClientIp } from "@/lib/validation";

export async function POST(request: NextRequest) {
  const body = await request.json();
  const { email, password, first_name, last_name, company_name, phone_number } =
    body;

  // Validate required fields
  if (!email || !password || !first_name || !last_name) {
    return NextResponse.json(
      { error: "Email, password, first name, and last name are required" },
      { status: 400 }
    );
  }

  // Validate email format
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email)) {
    return NextResponse.json(
      { error: "Please enter a valid email address" },
      { status: 400 }
    );
  }

  // Validate password strength
  const passwordError = validatePassword(password);
  if (passwordError) {
    return NextResponse.json({ error: passwordError }, { status: 400 });
  }

  const supabase = await createServiceRoleClient();

  // Create auth user via signUp (sends verification email)
  const { data: authData, error: authError } =
    await supabase.auth.admin.createUser({
      email,
      password,
      email_confirm: false,
    });

  if (authError) {
    if (authError.message?.includes("already been registered") || authError.message?.includes("already exists")) {
      return NextResponse.json(
        { error: "An account with this email already exists. Try signing in or resetting your password." },
        { status: 409 }
      );
    }
    return NextResponse.json(
      { error: "Failed to create account. Please try again." },
      { status: 400 }
    );
  }

  const authUserId = authData.user.id;

  // Create client record
  const fullName = `${first_name.trim()} ${last_name.trim()}`;
  const { data: client, error: clientError } = await supabase
    .from("clients")
    .insert({
      auth_user_id: authUserId,
      email: email.toLowerCase().trim(),
      full_name: fullName,
      company_name: company_name?.trim() || null,
      phone_number: phone_number?.trim() || null,
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

  // Send verification email
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";
  await supabase.auth.admin.generateLink({
    type: "signup",
    email,
    password,
    options: {
      redirectTo: `${appUrl}/portal/auth/callback`,
    },
  });

  // Log activity
  const ip = extractClientIp(request);
  await supabase.from("activity_log").insert({
    actor_type: "system",
    actor_id: client.id,
    action: "client_self_signup",
    target_type: "client",
    target_id: client.id,
    details: { email, full_name: fullName },
    ip_address: ip,
  });

  return NextResponse.json({ success: true }, { status: 201 });
}
