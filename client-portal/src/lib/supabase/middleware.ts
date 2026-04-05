import { createServerClient } from "@supabase/ssr";
import { createClient } from "@supabase/supabase-js";
import { NextResponse, type NextRequest } from "next/server";

// Service role client for RLS-bypassing queries in middleware
function getServiceClient() {
  return createClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.SUPABASE_SERVICE_ROLE_KEY!,
  );
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          );
          supabaseResponse = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const {
    data: { user },
  } = await supabase.auth.getUser();

  const pathname = request.nextUrl.pathname;

  // Protect /portal/* routes (except public auth pages)
  const publicPortalPaths = ["/portal/login", "/portal/signup", "/portal/reset-password", "/portal/auth/callback"];
  const isPublicPortalPath = publicPortalPaths.some(p => pathname.startsWith(p));
  if (pathname.startsWith("/portal") && !isPublicPortalPath) {
    if (!user) {
      const url = request.nextUrl.clone();
      url.pathname = "/portal/login";
      return NextResponse.redirect(url);
    }

    // Check if user is a financial adviser or FA client accessing advisory pages
    if (pathname.startsWith("/portal/advisory")) {
      const svc = getServiceClient();
      const { data: faAdviser } = await svc
        .from("fa_advisers")
        .select("id")
        .eq("auth_user_id", user.id)
        .maybeSingle();

      if (faAdviser) {
        return supabaseResponse;
      }

      const { data: portalClient } = await svc
        .from("clients")
        .select("id")
        .eq("auth_user_id", user.id)
        .maybeSingle();

      if (portalClient) {
        const { data: faClient } = await svc
          .from("fa_clients")
          .select("id")
          .eq("portal_client_id", portalClient.id)
          .maybeSingle();

        if (faClient) {
          return supabaseResponse;
        }
      }
    }

    // Verify user is actually a client (use service client to bypass RLS)
    const svcClient = getServiceClient();
    const { data: clientUser } = await svcClient
      .from("clients")
      .select("id, onboarding_completed_at")
      .eq("auth_user_id", user.id)
      .maybeSingle();

    if (!clientUser) {
      const url = request.nextUrl.clone();
      url.pathname = "/portal/login";
      return NextResponse.redirect(url);
    }

    // Onboarding redirect: if onboarding not completed, redirect to wizard
    // Allow access to onboarding page itself, billing, and settings
    const onboardingExemptPaths = ["/portal/onboarding", "/portal/billing", "/portal/settings"];
    const isOnboardingExempt = onboardingExemptPaths.some(p => pathname.startsWith(p));

    if (!clientUser.onboarding_completed_at && !isOnboardingExempt) {
      const url = request.nextUrl.clone();
      url.pathname = "/portal/onboarding";
      return NextResponse.redirect(url);
    }

    // Paywall: check for active subscription (skip billing, settings, advisory, onboarding pages)
    const billingExemptPaths = ["/portal/billing", "/portal/settings", "/portal/advisory", "/portal/onboarding"];
    const isBillingExempt = billingExemptPaths.some(p => pathname.startsWith(p));

    if (!isBillingExempt) {
      const { data: sub } = await svcClient
        .from("subscriptions")
        .select("status")
        .eq("client_id", clientUser.id)
        .in("status", ["active", "trialing", "past_due"])
        .limit(1)
        .maybeSingle();

      if (!sub) {
        const url = request.nextUrl.clone();
        url.pathname = "/portal/billing";
        url.searchParams.set("gate", "true");
        return NextResponse.redirect(url);
      }
    }
  }

  // Protect /admin/* routes (except /admin/login)
  if (pathname.startsWith("/admin") && !pathname.startsWith("/admin/login")) {
    if (!user) {
      const url = request.nextUrl.clone();
      url.pathname = "/admin/login";
      return NextResponse.redirect(url);
    }

    // Check admin role
    const { data: adminUser } = await supabase
      .from("admin_users")
      .select("role")
      .eq("auth_user_id", user.id)
      .maybeSingle();

    if (!adminUser) {
      // Also allow financial advisers to access /admin/advisory/*
      const svc = getServiceClient();
      const { data: faAdviser } = await svc
        .from("fa_advisers")
        .select("id, role")
        .eq("auth_user_id", user.id)
        .eq("active", true)
        .maybeSingle();

      if (!faAdviser) {
        const url = request.nextUrl.clone();
        url.pathname = "/admin/login";
        return NextResponse.redirect(url);
      }
    }
  }

  return supabaseResponse;
}
