"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, Eye, EyeOff, ShieldCheck } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { BlobBackground } from "@/components/portal/BlobBackground";
import { Card } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";
import { Input } from "@/components/ui-shadcn/input";
import { Field } from "@/components/ui-shadcn/field";
import { cn } from "@/lib/utils";

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8,               label: "At least 8 characters" },
  { test: (p: string) => /[A-Z]/.test(p),             label: "One uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p),             label: "One lowercase letter" },
  { test: (p: string) => /[0-9]/.test(p),             label: "One number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p), label: "One special character" },
];

export default function ResetPasswordPage() {
  const router = useRouter();
  const supabase = createClient();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") setReady(true);
    });
    return () => subscription.unsubscribe();
  }, [supabase]);

  async function handleReset(e: React.FormEvent) {
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
      setError("Failed to update password. Please try again.");
      setLoading(false);
      return;
    }

    setSuccess(true);
    setTimeout(() => {
      router.push("/portal");
    }, 2000);
  }

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      <BlobBackground intensity="hero" />
      <div className="relative z-[1] w-full max-w-[440px]">
        <div className="text-center mb-6">
          <div className="inline-flex items-center gap-2">
            <span className="grid place-items-center size-9 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]">
              <ShieldCheck className="size-5 text-white" aria-hidden />
            </span>
            <span className="text-base font-bold tracking-[0.08em] text-foreground">ANYVISION</span>
          </div>
        </div>

        <Card variant="default" accent="gradient-static" padding="lg" className="animate-fade-in-up">
          <h1 className="text-xl font-bold text-foreground">Reset password</h1>
          <p className="text-sm text-[var(--text-muted)] mt-1 mb-6">
            {ready
              ? "Enter your new password below."
              : success
                ? "Redirecting you to the portal…"
                : "Processing your reset link…"}
          </p>

          {success ? (
            <div className="text-center flex flex-col items-center gap-3">
              <span className="grid place-items-center size-12 rounded-full bg-[color-mix(in_srgb,var(--accent-teal)_15%,transparent)] text-[var(--accent-teal)]">
                <Check className="size-5" />
              </span>
              <p className="text-base font-semibold text-foreground">Password updated!</p>
              <p className="text-sm text-[var(--text-muted)]">Redirecting you to the portal…</p>
            </div>
          ) : ready ? (
            <form onSubmit={handleReset} className="flex flex-col gap-5">
              <Field label="New password" required>
                <div className="relative">
                  <Input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter new password"
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
                label="Confirm new password"
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
                    placeholder="Confirm new password"
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
                Update password
              </Button>
            </form>
          ) : (
            <div className="text-center flex flex-col items-center gap-3">
              <p className="text-sm text-[var(--text-muted)]">
                This page is for password reset links sent via email.
              </p>
              <Button asChild variant="outline" size="sm">
                <Link href="/portal/login">Go to login</Link>
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
