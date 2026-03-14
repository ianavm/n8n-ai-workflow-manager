import { NextResponse, type NextRequest } from "next/server";
import { updateSession } from "@/lib/supabase/middleware";
import { rateLimit } from "@/lib/rate-limit";

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

  if ((isLoginPath || isAuthApi) && request.method === "POST") {
    const ip =
      request.headers.get("x-forwarded-for")?.split(",")[0].trim() ??
      "unknown";
    const { allowed, remaining, resetAt } = rateLimit(ip);

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

    // Add rate limit headers to the response
    const response = await updateSession(request);
    response.headers.set("X-RateLimit-Remaining", String(remaining));
    return response;
  }

  return await updateSession(request);
}

export const config = {
  matcher: ["/portal/:path*", "/admin/:path*", "/api/auth/:path*", "/portal/auth/callback", "/api/billing/:path*"],
};
