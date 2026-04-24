"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Image from "next/image";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Check, Lock, Mail, ShieldCheck } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { useBrand } from "@/lib/providers/BrandProvider";
import { BlobBackground } from "@/components/portal/BlobBackground";
import { Card } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";
import { Input } from "@/components/ui-shadcn/input";
import { Field } from "@/components/ui-shadcn/field";
import { Checkbox } from "@/components/ui-shadcn/checkbox";
import { Separator } from "@/components/ui-shadcn/separator";
import { cn } from "@/lib/utils";

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  signups_closed:
    "New signups are closed. Contact ian@anyvisionmedia.com to request portal access.",
  signup_failed: "Sign-in failed. Please try again or contact support.",
};

type Mode = "password" | "magic" | "reset";

export default function PortalLoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();
  const { companyName, logoUrl, isCustomBranded } = useBrand();

  const [mode, setMode] = useState<Mode>("password");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  useEffect(() => {
    const errParam = searchParams?.get("error");
    if (errParam && LOGIN_ERROR_MESSAGES[errParam]) {
      setError(LOGIN_ERROR_MESSAGES[errParam]);
    }
  }, [searchParams]);

  const companyDisplay = isCustomBranded ? companyName.toUpperCase() : "ANYVISION MEDIA";

  function resetFlow() {
    setMode("password");
    setError("");
    setMagicLinkSent(false);
    setResetSent(false);
  }

  async function handleGoogleLogin() {
    setError("");
    setGoogleLoading(true);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/portal/auth/callback`,
        queryParams: { prompt: "select_account" },
      },
    });
    if (oauthError) {
      setError("Failed to connect with Google. Please try again.");
      setGoogleLoading(false);
    }
  }

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { error: magicError } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: `${window.location.origin}/portal/auth/callback` },
    });
    if (magicError) {
      setError("Failed to send sign-in link. Please try again.");
    } else {
      setMagicLinkSent(true);
    }
    setLoading(false);
  }

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { error: authError } = await supabase.auth.signInWithPassword({ email, password });
    if (authError) {
      setError("Invalid email or password");
      setLoading(false);
      return;
    }

    try {
      const res = await fetch("/api/auth/check-role");
      if (!res.ok) {
        window.location.href = "/portal";
        return;
      }
      const { redirect } = await res.json();
      const target = redirect || "/portal";
      if (target === "/portal/login") {
        setError("Account not found. Please contact support.");
        setLoading(false);
        return;
      }
      fetch("/api/auth/record-login", { method: "POST" }).catch(() => {});
      window.location.href = target;
    } catch {
      fetch("/api/auth/record-login", { method: "POST" }).catch(() => {});
      window.location.href = "/portal";
    }
  }

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/portal/reset-password`,
    });
    if (resetError) {
      setError("Failed to send reset email. Please try again.");
    } else {
      setResetSent(true);
    }
    setLoading(false);
  }

  // Route back to appropriate router after actions if needed
  void router;

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      <BlobBackground intensity="hero" />
      <div className="relative z-[1] w-full max-w-[440px]">
        <Card variant="default" accent="gradient-static" padding="lg" className="animate-fade-in-up">
          {/* Brand */}
          <div className="text-center mb-6">
            {logoUrl ? (
              <Image
                src={logoUrl}
                alt={companyName}
                width={180}
                height={40}
                className="mx-auto max-h-10 object-contain"
                unoptimized
              />
            ) : (
              <div className="flex items-center justify-center gap-2">
                <span className="grid place-items-center size-9 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]">
                  <ShieldCheck className="size-5 text-white" aria-hidden />
                </span>
                <span className="text-base font-bold tracking-[0.08em] text-foreground">
                  {companyDisplay}
                </span>
              </div>
            )}
            <p className="text-sm text-[var(--text-muted)] mt-3">
              {mode === "reset"
                ? "Reset your password"
                : mode === "magic"
                  ? "Sign in with email link"
                  : "Sign in to your portal"}
            </p>
          </div>

          {/* Confirmations */}
          {resetSent ? (
            <ConfirmationView
              icon={<Check className="size-5" />}
              title="Check your email"
              message={`We sent a password reset link to ${email}`}
              onBack={resetFlow}
            />
          ) : magicLinkSent ? (
            <ConfirmationView
              icon={<Mail className="size-5" />}
              title="Check your email"
              message={`We sent a sign-in link to ${email}`}
              onBack={resetFlow}
            />
          ) : (
            <>
              {/* Google SSO */}
              {mode === "password" ? (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="lg"
                    onClick={handleGoogleLogin}
                    loading={googleLoading}
                    disabled={googleLoading}
                    className={cn(
                      "w-full bg-white text-[#202124] hover:bg-gray-50 hover:text-[#202124]",
                      "border-[rgba(0,0,0,0.08)]",
                    )}
                  >
                    {!googleLoading ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden>
                        <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                        <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                        <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                        <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                      </svg>
                    ) : null}
                    {googleLoading ? "Connecting…" : "Continue with Google"}
                  </Button>
                  <div className="flex items-center gap-3 my-5">
                    <Separator className="flex-1" />
                    <span className="text-[10px] font-semibold uppercase tracking-[0.12em] text-[var(--text-dim)]">
                      or
                    </span>
                    <Separator className="flex-1" />
                  </div>
                </>
              ) : null}

              <form
                onSubmit={
                  mode === "reset" ? handleReset : mode === "magic" ? handleMagicLink : handleLogin
                }
                className="flex flex-col gap-4"
              >
                <Field label="Email address" required>
                  <Input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@company.co.za"
                    autoComplete="email"
                    required
                  />
                </Field>

                {mode === "password" ? (
                  <Field label="Password" required>
                    <Input
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Enter your password"
                      autoComplete="current-password"
                      required
                    />
                  </Field>
                ) : null}

                {mode === "password" ? (
                  <div className="flex items-center justify-between -mt-1">
                    <label className="flex items-center gap-2 text-xs text-[var(--text-muted)] cursor-pointer">
                      <Checkbox />
                      Remember me
                    </label>
                    <button
                      type="button"
                      onClick={() => {
                        setMode("reset");
                        setError("");
                      }}
                      className="text-xs font-medium text-[var(--brand-primary)] hover:underline"
                    >
                      Forgot password?
                    </button>
                  </div>
                ) : null}

                {error ? (
                  <p
                    role="alert"
                    className="text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_25%,transparent)] rounded-[var(--radius-sm)] px-3 py-2"
                  >
                    {error}
                  </p>
                ) : null}

                <Button type="submit" variant="default" size="lg" loading={loading} className="w-full">
                  {mode === "reset"
                    ? "Send reset link"
                    : mode === "magic"
                      ? "Send sign-in link"
                      : "Sign in"}
                </Button>

                {mode === "password" ? (
                  <button
                    type="button"
                    onClick={() => {
                      setMode("magic");
                      setError("");
                    }}
                    className="text-center text-xs text-[var(--text-muted)] inline-flex items-center justify-center gap-1.5 hover:text-foreground transition-colors"
                  >
                    <Mail className="size-3.5" />
                    Sign in with email link instead
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={resetFlow}
                    className="text-center text-xs font-medium text-[var(--brand-primary)] inline-flex items-center justify-center gap-1.5 hover:underline"
                  >
                    <ArrowLeft className="size-3.5" />
                    Back to login
                  </button>
                )}
              </form>
            </>
          )}
        </Card>

        {/* Trust signals */}
        <div className="flex items-center justify-center gap-6 mt-8 text-xs text-[var(--text-dim)]">
          <span className="inline-flex items-center gap-1.5">
            <Lock className="size-3.5" />
            256-bit encrypted
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="size-3.5" />
            POPIA compliant
          </span>
        </div>

        {/* Legal links */}
        <div className="flex items-center justify-center gap-4 mt-4 text-xs text-[var(--text-dim)]">
          <Link href="/portal/legal/privacy" className="hover:text-[var(--text-muted)]">
            Privacy
          </Link>
          <Link href="/portal/legal/terms" className="hover:text-[var(--text-muted)]">
            Terms
          </Link>
          <a href="https://www.anyvisionmedia.com" className="hover:text-[var(--text-muted)]">
            ← anyvisionmedia.com
          </a>
        </div>
      </div>
    </div>
  );
}

function ConfirmationView({
  icon,
  title,
  message,
  onBack,
}: {
  icon: React.ReactNode;
  title: string;
  message: string;
  onBack: () => void;
}) {
  return (
    <div className="text-center flex flex-col items-center gap-3">
      <span className="grid place-items-center size-12 rounded-full bg-[color-mix(in_srgb,var(--accent-teal)_15%,transparent)] text-[var(--accent-teal)]">
        {icon}
      </span>
      <p className="text-base font-semibold text-foreground">{title}</p>
      <p className="text-sm text-[var(--text-muted)]">{message}</p>
      <Button variant="ghost" size="sm" onClick={onBack} className="mt-2">
        <ArrowLeft className="size-3.5" />
        Back to login
      </Button>
    </div>
  );
}
