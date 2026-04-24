"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Lock, Shield, ShieldAlert } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

function formatCountdown(totalSeconds: number): string {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes <= 0) return `${seconds}s`;
  if (seconds === 0) return `${minutes}m`;
  return `${minutes}m ${seconds}s`;
}

export default function AdminLoginPage() {
  const router = useRouter();
  const supabase = createClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  // Lockout state
  const [attemptsRemaining, setAttemptsRemaining] = useState<number | null>(null);
  const [lockoutExpiresAt, setLockoutExpiresAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const emailDebounce = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!lockoutExpiresAt) return;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [lockoutExpiresAt]);

  const checkLockout = useCallback(async (value: string) => {
    const normalized = value.trim().toLowerCase();
    if (!normalized || !normalized.includes("@")) {
      setAttemptsRemaining(null);
      setLockoutExpiresAt(null);
      return;
    }
    try {
      const res = await fetch("/api/auth/lockout-check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: normalized }),
      });
      const data = await res.json().catch(() => null);
      if (!data) return;
      setAttemptsRemaining(typeof data.remaining === "number" ? data.remaining : null);
      if (data.locked && typeof data.retryAfterSeconds === "number") {
        setLockoutExpiresAt(Date.now() + data.retryAfterSeconds * 1000);
      } else {
        setLockoutExpiresAt(null);
      }
    } catch {
      /* silent */
    }
  }, []);

  useEffect(() => {
    if (emailDebounce.current) clearTimeout(emailDebounce.current);
    emailDebounce.current = setTimeout(() => checkLockout(email), 400);
    return () => {
      if (emailDebounce.current) clearTimeout(emailDebounce.current);
    };
  }, [email, checkLockout]);

  const lockoutSecondsLeft = lockoutExpiresAt
    ? Math.max(0, Math.ceil((lockoutExpiresAt - now) / 1000))
    : 0;
  const isLockedOut = lockoutSecondsLeft > 0;

  async function recordFailedLogin() {
    try {
      const res = await fetch("/api/auth/record-failed-login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json().catch(() => null);
      if (!data) return;
      if (typeof data.remaining === "number") setAttemptsRemaining(data.remaining);
      if (data.locked && typeof data.retryAfterSeconds === "number") {
        setLockoutExpiresAt(Date.now() + data.retryAfterSeconds * 1000);
      }
    } catch {
      /* silent */
    }
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    if (isLockedOut) return;
    setError("");
    setLoading(true);

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      await recordFailedLogin();
      setError(authError.message);
      setLoading(false);
      return;
    }

    // Success — clear lockout state
    setAttemptsRemaining(null);
    setLockoutExpiresAt(null);

    try {
      const res = await fetch("/api/auth/check-role");
      if (!res.ok) {
        await supabase.auth.signOut();
        setError("Unable to verify access. Please try again.");
        setLoading(false);
        return;
      }
      const { role, redirect } = await res.json();

      if (!role || role === "client") {
        await supabase.auth.signOut();
        setError("This account does not have admin access");
        setLoading(false);
        return;
      }

      window.location.href = redirect || "/admin";
    } catch {
      await supabase.auth.signOut();
      setError("Unable to verify access. Please try again.");
      setLoading(false);
    }
  }

  // Suppress unused-router warning (retained for future routing logic)
  void router;

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg relative animate-fade-in-up">
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2.5 mb-4">
            <Shield size={28} className="text-[var(--accent-purple)]" />
            <span className="text-2xl font-bold text-foreground">
              AnyVision<span className="text-[var(--accent-teal)]">.</span>
            </span>
          </div>
          <h1 className="text-2xl font-bold text-foreground">Admin Dashboard</h1>
          <p className="text-sm text-[var(--text-dim)] mt-2">Internal access only</p>
        </div>

        <div className="glass-card p-10">
          <form onSubmit={handleLogin} className="space-y-5">
            <Input
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              required
              autoComplete="email"
            />

            <Input
              label="Password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              autoComplete="current-password"
            />

            {/* Lockout banner */}
            {isLockedOut ? (
              <div
                role="alert"
                className="flex items-start gap-2 text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_25%,transparent)] rounded-lg px-3 py-2.5"
              >
                <ShieldAlert className="size-4 shrink-0 mt-0.5" aria-hidden />
                <div>
                  <p className="font-semibold">Too many failed attempts</p>
                  <p className="text-[var(--text-muted)] mt-0.5">
                    Try again in {formatCountdown(lockoutSecondsLeft)}.
                  </p>
                </div>
              </div>
            ) : null}

            {!isLockedOut &&
            attemptsRemaining !== null &&
            attemptsRemaining <= 2 &&
            attemptsRemaining > 0 ? (
              <p className="text-xs text-[var(--warning)] inline-flex items-center gap-1.5">
                <ShieldAlert className="size-3.5" aria-hidden />
                {attemptsRemaining === 1
                  ? "1 attempt remaining before lockout."
                  : `${attemptsRemaining} attempts remaining before lockout.`}
              </p>
            ) : null}

            {error ? (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            ) : null}

            <Button
              type="submit"
              variant="primary"
              loading={loading}
              disabled={isLockedOut}
              className="w-full"
            >
              Sign In
            </Button>
          </form>
        </div>
      </div>

      <div className="flex items-center gap-1.5 mt-8 text-[12px] text-[var(--text-dim)]">
        <Lock size={13} />
        <span>Secured connection</span>
      </div>
    </div>
  );
}
