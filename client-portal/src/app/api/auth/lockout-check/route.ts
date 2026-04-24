import { NextRequest, NextResponse } from "next/server";

import { peekRateLimit } from "@/lib/rate-limit";
import { extractClientIp } from "@/lib/validation";

/**
 * Passive pre-auth lockout check.
 *
 * Returns the current lockout state without consuming a slot. The login
 * UI calls this before submitting credentials so it can show the "too
 * many failed attempts" countdown immediately on page load / refresh.
 *
 * Bucket key: `login:<email>:<ip>` in the `strict` profile
 * (5 attempts / 30 min).
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
  const result = await peekRateLimit(`login:${email}:${ip}`, "strict");
  const retryAfterSeconds = Math.max(0, Math.ceil((result.resetAt - Date.now()) / 1000));

  if (result.locked) {
    return NextResponse.json(
      {
        locked: true,
        remaining: 0,
        retryAfterSeconds,
      },
      {
        status: 429,
        headers: { "Retry-After": String(retryAfterSeconds) },
      },
    );
  }

  return NextResponse.json({
    locked: false,
    remaining: result.remaining,
    retryAfterSeconds,
  });
}
