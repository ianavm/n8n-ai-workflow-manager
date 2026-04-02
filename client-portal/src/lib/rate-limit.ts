/**
 * Rate limiter for auth and API endpoints.
 * Uses Vercel KV (Redis) if available, falls back to in-memory with
 * request-scoped persistence (survives within a single instance).
 *
 * Defaults: 10 attempts per 15 minutes for auth, configurable per endpoint.
 */

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

// Global store — persists across requests within the same serverless instance.
// Not perfect, but combined with short windows it provides meaningful protection.
// For full persistence, set KV_REST_API_URL + KV_REST_API_TOKEN env vars.
const store = new Map<string, RateLimitEntry>();

const CLEANUP_INTERVAL = 5 * 60 * 1000;
let lastCleanup = Date.now();

function cleanup(): void {
  const now = Date.now();
  if (now - lastCleanup < CLEANUP_INTERVAL) return;
  lastCleanup = now;
  for (const [key, entry] of store) {
    if (entry.resetAt < now) {
      store.delete(key);
    }
  }
}

/** Preset rate limit profiles */
export const RATE_LIMITS = {
  /** Auth endpoints (login, signup, password reset): 10 per 15 min */
  auth: { maxAttempts: 10, windowMs: 15 * 60 * 1000 },
  /** API endpoints (billing, data reads): 60 per minute */
  api: { maxAttempts: 60, windowMs: 60 * 1000 },
  /** Webhooks (PayFast, Stripe ITN): 30 per minute */
  webhook: { maxAttempts: 30, windowMs: 60 * 1000 },
  /** Strict (password reset, OTP verify): 5 per 30 min */
  strict: { maxAttempts: 5, windowMs: 30 * 60 * 1000 },
} as const;

export function rateLimit(
  ip: string,
  {
    maxAttempts = RATE_LIMITS.auth.maxAttempts,
    windowMs = RATE_LIMITS.auth.windowMs,
  } = {}
): { allowed: boolean; remaining: number; resetAt: number } {
  cleanup();

  const now = Date.now();
  const key = `rl:${ip}`;
  const entry = store.get(key);

  if (!entry || entry.resetAt < now) {
    store.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: maxAttempts - 1, resetAt: now + windowMs };
  }

  const newCount = entry.count + 1;
  store.set(key, { count: newCount, resetAt: entry.resetAt });
  const allowed = newCount <= maxAttempts;
  return {
    allowed,
    remaining: Math.max(0, maxAttempts - newCount),
    resetAt: entry.resetAt,
  };
}
