import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";
import { rateLimitAsync } from "@/lib/rate-limit";

// Signup paths get the strict limiter (5 per 30 min) — same tier applies to
// password reset. Other auth surfaces use the looser auth limiter (10 per 15 min).
const STRICT_PATHS = new Set([
  "/portal/signup",
  "/api/auth/signup",
  "/api/auth/reset-password",
  "/api/auth/invite",
]);

export async function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Skip middleware for webhook endpoints (PayFast ITN needs unauthenticated access)
  if (pathname.startsWith("/api/webhooks/")) {
    return NextResponse.next();
  }

  // Rate limit login pages and auth API endpoints to prevent brute force
  const isLoginPath =
    pathname === "/portal/login" || pathname === "/admin/login" || pathname === "/portal/signup";
  const isAuthApi = pathname.startsWith("/api/auth/");

  if (isLoginPath || isAuthApi) {
    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0].trim() ??
      "unknown";
    const profile = STRICT_PATHS.has(pathname) ? "strict" : "auth";
    const { allowed, remaining, resetAt } = await rateLimitAsync(ip, profile);

    if (!allowed) {
      const retryAfter = Math.ceil((resetAt - Date.now()) / 1000);
      return NextResponse.json(
        { error: "Too many attempts. Please try again later." },
        {
          status: 429,
          headers: {
            "Retry-After": String(retryAfter),
            "X-RateLimit-Remaining": "0",
          },
        }
      );
    }

    const response = await updateSession(request);
    response.headers.set("X-RateLimit-Remaining", String(remaining));
    return response;
  }

  return await updateSession(request);
}

export const config = {
  matcher: ["/portal/:path*", "/admin/:path*", "/api/auth/:path*", "/api/advisory/:path*", "/portal/auth/callback", "/api/billing/:path*"],
};
