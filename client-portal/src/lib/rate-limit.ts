/**
 * Rate limiter for auth and API endpoints.
 *
 * Uses Upstash Redis if UPSTASH_REDIS_REST_URL is set (recommended for production).
 * Falls back to in-memory store for local development.
 */

import { Ratelimit } from "@upstash/ratelimit";
import { Redis } from "@upstash/redis";

// ---------- In-memory fallback (dev / missing env vars) ----------

interface RateLimitEntry {
  count: number;
  resetAt: number;
}

const memoryStore = new Map<string, RateLimitEntry>();
const CLEANUP_INTERVAL = 5 * 60 * 1000;
let lastCleanup = Date.now();

function cleanupMemory(): void {
  const now = Date.now();
  if (now - lastCleanup < CLEANUP_INTERVAL) return;
  lastCleanup = now;
  for (const [key, entry] of memoryStore) {
    if (entry.resetAt < now) {
      memoryStore.delete(key);
    }
  }
}

function memoryRateLimit(
  ip: string,
  maxAttempts: number,
  windowMs: number
): { allowed: boolean; remaining: number; resetAt: number } {
  cleanupMemory();
  const now = Date.now();
  const key = `rl:${ip}`;
  const entry = memoryStore.get(key);

  if (!entry || entry.resetAt < now) {
    memoryStore.set(key, { count: 1, resetAt: now + windowMs });
    return { allowed: true, remaining: maxAttempts - 1, resetAt: now + windowMs };
  }

  const newCount = entry.count + 1;
  memoryStore.set(key, { count: newCount, resetAt: entry.resetAt });
  const allowed = newCount <= maxAttempts;
  return {
    allowed,
    remaining: Math.max(0, maxAttempts - newCount),
    resetAt: entry.resetAt,
  };
}

// ---------- Upstash Redis rate limiters ----------

const hasUpstash = !!(process.env.UPSTASH_REDIS_REST_URL && process.env.UPSTASH_REDIS_REST_TOKEN);

const redis = hasUpstash
  ? new Redis({
      url: process.env.UPSTASH_REDIS_REST_URL!,
      token: process.env.UPSTASH_REDIS_REST_TOKEN!,
    })
  : null;

const upstashLimiters = redis
  ? {
      auth: new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(10, "15 m") }),
      api: new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(60, "1 m") }),
      webhook: new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(30, "1 m") }),
      strict: new Ratelimit({ redis, limiter: Ratelimit.slidingWindow(5, "30 m") }),
    }
  : null;

// ---------- Public API ----------

/** Preset rate limit profiles */
export const RATE_LIMITS = {
  auth: { maxAttempts: 10, windowMs: 15 * 60 * 1000 },
  api: { maxAttempts: 60, windowMs: 60 * 1000 },
  webhook: { maxAttempts: 30, windowMs: 60 * 1000 },
  strict: { maxAttempts: 5, windowMs: 30 * 60 * 1000 },
} as const;

type ProfileName = keyof typeof RATE_LIMITS;

export function rateLimit(
  ip: string,
  {
    maxAttempts = RATE_LIMITS.auth.maxAttempts,
    windowMs = RATE_LIMITS.auth.windowMs,
    profile,
  }: {
    maxAttempts?: number;
    windowMs?: number;
    profile?: ProfileName;
  } = {}
): { allowed: boolean; remaining: number; resetAt: number } {
  // If Upstash is available and a profile name is given, use distributed limiter
  // (async version is preferred, but we keep sync API for backwards compat)
  return memoryRateLimit(ip, maxAttempts, windowMs);
}

/**
 * Async rate limit using Upstash Redis when available.
 * Falls back to in-memory when Upstash is not configured.
 */
export async function rateLimitAsync(
  ip: string,
  profile: ProfileName = "auth"
): Promise<{ allowed: boolean; remaining: number; resetAt: number }> {
  if (upstashLimiters) {
    const limiter = upstashLimiters[profile];
    const result = await limiter.limit(ip);
    return {
      allowed: result.success,
      remaining: result.remaining,
      resetAt: result.reset,
    };
  }

  const config = RATE_LIMITS[profile];
  return memoryRateLimit(ip, config.maxAttempts, config.windowMs);
}
