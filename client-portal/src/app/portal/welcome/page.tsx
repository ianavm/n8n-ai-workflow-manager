"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Check, Eye, EyeOff, ShieldCheck, Sparkles } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { BlobBackground } from "@/components/portal/BlobBackground";
import { Card } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";
import { Input } from "@/components/ui-shadcn/input";
import { Field } from "@/components/ui-shadcn/field";
import { cn } from "@/lib/utils";

// Identical password rules to /portal/reset-password — keep them in sync if
// either ever moves. Five checks; all must pass.
const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8,                            label: "At least 8 characters" },
  { test: (p: string) => /[A-Z]/.test(p),                          label: "One uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p),                          label: "One lowercase letter" },
  { test: (p: string) => /[0-9]/.test(p),                          label: "One number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p),         label: "One special character" },
];

/**
 * /portal/welcome — landing page for newly invited users.
 *
 * Supabase invite flow:
 *   1. Admin or manager calls inviteUserByEmail() → user gets an email
 *   2. User clicks the link → Supabase verifies the token → SIGNED_IN event
 *      fires with the user authenticated but NO password set
 *   3. They land here. We force them to set a password before continuing,
 *      otherwise they'd be locked out next session (no email+password sign-in
 *      possible until a password exists).
 *
 * Distinct from /portal/reset-password (that one fires on PASSWORD_RECOVERY,
 * triggered by a different email template).
 */
export default function WelcomePage() {
  const router = useRouter();
  const supabase = createClient();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [authed, setAuthed] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [displayName, setDisplayName] = useState<string>("");
  const [companyName, setCompanyName] = useState<string>("");

  useEffect(() => {
    // Initial check — if the auth-token-in-URL fragment has already been
    // processed by the supabase client, getUser() returns the new user
    // immediately. Otherwise we wait for the SIGNED_IN event.
    let cancelled = false;

    async function init() {
      const { data: { user } } = await supabase.auth.getUser();
      if (cancelled) return;
      if (user) {
        setAuthed(true);
        const meta = (user.user_metadata ?? {}) as { full_name?: string; company_name?: string };
        if (meta.full_name) setDisplayName(meta.full_name.split(" ")[0]);
        if (meta.company_name) setCompanyName(meta.company_name);
      }
    }
    init();

    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (event, session) => {
        if (event === "SIGNED_IN" && session?.user) {
          setAuthed(true);
          const meta = (session.user.user_metadata ?? {}) as {
            full_name?: string;
            company_name?: string;
          };
          if (meta.full_name) setDisplayName(meta.full_name.split(" ")[0]);
          if (meta.company_name) setCompanyName(meta.company_name);
        }
      },
    );

    return () => {
      cancelled = true;
      subscription.unsubscribe();
    };
  }, [supabase]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (!PASSWORD_RULES.every((r) => r.test(password))) {
      setError("Password does not meet all requirements");
      return;
    }

    setLoading(true);
    const { error: updateError } = await supabase.auth.updateUser({ password });
    if (updateError) {
      setError("Failed to set password. Please try again.");
      setLoading(false);
      return;
    }

    setSuccess(true);
    setTimeout(() => {
      // Newly invited users go through onboarding first; the onboarding flow
      // hands off to /portal once complete.
      router.push("/portal/onboarding");
    }, 1500);
  }

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      <BlobBackground intensity="hero" />
      <div className="relative z-[1] w-full max-w-[460px]">
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2">
            <span className="grid place-items-center size-9 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]">
              <ShieldCheck className="size-5 text-white" aria-hidden />
            </span>
            <span className="text-base font-bold tracking-[0.08em] text-foreground">ANYVISION</span>
          </div>
        </div>

        <Card variant="default" accent="gradient-static" padding="lg" className="animate-fade-in-up">
          <div className="flex items-center gap-2 mb-2">
            <Sparkles className="size-4 text-[var(--brand-primary)]" aria-hidden />
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--brand-primary)]">
              Welcome
            </p>
          </div>
          <h1 className="text-xl font-bold text-foreground">
            {displayName ? `Hi ${displayName} —` : "Hi there —"} let&apos;s set your password
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-1 mb-6">
            {success
              ? "All set. Taking you to onboarding…"
              : authed
                ? companyName
                  ? `You've been invited to the ${companyName} portal. Pick a password to finish setting up your account.`
                  : "Pick a password to finish setting up your account."
                : "Verifying your invite link…"}
          </p>

          {success ? (
            <div className="text-center flex flex-col items-center gap-3">
              <span className="grid place-items-center size-12 rounded-full bg-[color-mix(in_srgb,var(--accent-teal)_15%,transparent)] text-[var(--accent-teal)]">
                <Check className="size-5" />
              </span>
              <p className="text-base font-semibold text-foreground">Password set!</p>
              <p className="text-sm text-[var(--text-muted)]">Taking you to onboarding…</p>
            </div>
          ) : authed ? (
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              <Field label="Choose a password" required>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter a password"
                    autoComplete="new-password"
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] hover:text-foreground"
                  >
                    {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </Field>

              {password ? (
                <ul className="flex flex-col gap-1.5 px-1">
                  {PASSWORD_RULES.map((rule) => {
                    const passed = rule.test(password);
                    return (
                      <li key={rule.label} className="flex items-center gap-2 text-xs">
                        <span
                          className={cn(
                            "size-3.5 shrink-0 rounded-full grid place-items-center",
                            passed
                              ? "bg-[color-mix(in_srgb,var(--accent-teal)_20%,transparent)] text-[var(--accent-teal)]"
                              : "bg-[color-mix(in_srgb,var(--text-white)_5%,transparent)] text-[var(--text-dim)]",
                          )}
                          aria-hidden
                        >
                          {passed ? <Check className="size-2.5" /> : null}
                        </span>
                        <span className={passed ? "text-foreground" : "text-[var(--text-dim)]"}>
                          {rule.label}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : null}

              <Field
                label="Confirm password"
                required
                error={
                  confirmPassword && password !== confirmPassword
                    ? "Passwords do not match"
                    : undefined
                }
              >
                <div className="relative">
                  <Input
                    type={showConfirm ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Re-enter password"
                    autoComplete="new-password"
                    required
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirm((v) => !v)}
                    tabIndex={-1}
                    aria-label={showConfirm ? "Hide password" : "Show password"}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] hover:text-foreground"
                  >
                    {showConfirm ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                  </button>
                </div>
              </Field>

              {error ? (
                <p
                  role="alert"
                  className="text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_25%,transparent)] rounded-[var(--radius-sm)] px-3 py-2"
                >
                  {error}
                </p>
              ) : null}

              <Button type="submit" variant="default" size="lg" loading={loading} className="w-full">
                Set password & continue
              </Button>
            </form>
          ) : (
            <div className="text-center flex flex-col items-center gap-3">
              <p className="text-sm text-[var(--text-muted)]">
                This page is for invited users. If your invite link expired, ask
                whoever invited you to send a fresh one.
              </p>
              <Button asChild variant="outline" size="sm">
                <a href="/portal/login">Go to login</a>
              </Button>
            </div>
          )}
        </Card>

        <p className="text-center text-xs text-[var(--text-dim)] mt-6">
          <a
            href="https://www.anyvisionmedia.com"
            className="hover:text-[var(--text-muted)] transition-colors"
          >
            ← Back to anyvisionmedia.com
          </a>
        </p>
      </div>
    </div>
  );
}
