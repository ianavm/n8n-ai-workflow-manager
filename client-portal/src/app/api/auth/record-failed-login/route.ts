import { NextRequest, NextResponse } from "next/server";

import { rateLimitAsync } from "@/lib/rate-limit";
import { extractClientIp } from "@/lib/validation";

/**
 * Records a failed login attempt and returns the current lockout status.
 *
 * The client calls this only AFTER a genuinely failed
 * `supabase.auth.signInWithPassword` — so successful logins never
 * increment the counter.
 *
 * Bucket key: `login:<email>:<ip>` in the `strict` profile
 * (5 attempts / 30 min). On the 6th call the client is locked out.
 */
export async function POST(request: NextRequest) {
  let body: { email?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!email) {
    return NextResponse.json({ error: "Email is required" }, { status: 400 });
  }

  const ip = extractClientIp(request);
  const result = await rateLimitAsync(`login:${email}:${ip}`, "strict");
  const retryAfterSeconds = Math.max(0, Math.ceil((result.resetAt - Date.now()) / 1000));
  const locked = !result.allowed || result.remaining <= 0;

  return NextResponse.json(
    {
      locked,
      remaining: result.remaining,
      retryAfterSeconds,
    },
    locked
      ? { status: 429, headers: { "Retry-After": String(retryAfterSeconds) } }
      : undefined,
  );
}
