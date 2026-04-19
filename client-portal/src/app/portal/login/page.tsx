"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { useRouter, useSearchParams } from "next/navigation";
import { Check, Mail, Lock, ShieldCheck } from "lucide-react";
import { useTheme } from "@/lib/theme-provider";
import Image from "next/image";

const LOGIN_ERROR_MESSAGES: Record<string, string> = {
  signups_closed:
    "New signups are closed. Contact ian@anyvisionmedia.com to request portal access.",
  signup_failed: "Sign-in failed. Please try again or contact support.",
};

export default function PortalLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [resetSent, setResetSent] = useState(false);
  const [magicLinkMode, setMagicLinkMode] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const supabase = createClient();
  const theme = useTheme();

  useEffect(() => {
    const errParam = searchParams?.get("error");
    if (errParam && LOGIN_ERROR_MESSAGES[errParam]) {
      setError(LOGIN_ERROR_MESSAGES[errParam]);
    }
  }, [searchParams]);

  async function handleGoogleLogin() {
    setError("");
    setGoogleLoading(true);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/portal/auth/callback`,
        queryParams: {
          prompt: "select_account",
        },
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
      options: {
        emailRedirectTo: `${window.location.origin}/portal/auth/callback`,
      },
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

    const { error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

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
      // Record login metadata (fire-and-forget, don't block redirect)
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

    const { error: resetError } = await supabase.auth.resetPasswordForEmail(
      email,
      { redirectTo: `${window.location.origin}/portal/reset-password` }
    );

    if (resetError) {
      setError("Failed to send reset email. Please try again.");
    } else {
      setResetSent(true);
    }
    setLoading(false);
  }

  const brandColor = theme.brandColor || "#6366F1";

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      {/* Login card */}
      <div className="animate-fade-in-up w-full max-w-[440px] bg-[#1C1C22] border border-[rgba(255,255,255,0.08)] rounded-lg p-10 relative">
        {/* Top accent line */}
        <div
          className="absolute top-0 left-0 right-0 h-[3px] rounded-t-lg"
          style={{ background: brandColor }}
        />

        {/* Logo */}
        <div className="text-center mb-8">
          {theme.logoUrl ? (
            <Image
              src={theme.logoUrl}
              alt={theme.companyName}
              width={180}
              height={40}
              className="mx-auto max-h-10 object-contain"
              unoptimized
            />
          ) : (
            <div className="flex items-center justify-center gap-2 mb-2">
              <ShieldCheck size={28} style={{ color: brandColor }} />
              <span className="text-xl font-bold tracking-wide text-white">
                {theme.isCustomBranded ? theme.companyName.toUpperCase() : "ANYVISION MEDIA"}
              </span>
            </div>
          )}
          <div className="text-sm text-[#71717A] mt-3">
            {resetMode ? "Reset your password" : magicLinkMode ? "Sign in with email link" : "Sign in to your portal"}
          </div>
        </div>

        {/* Reset sent confirmation */}
        {resetSent && (
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 mx-auto mb-4 flex items-center justify-center text-emerald-400">
              <Check size={24} />
            </div>
            <p className="text-white font-medium mb-2">Check your email</p>
            <p className="text-sm text-[#71717A] mb-5">
              We sent a password reset link to {email}
            </p>
            <button
              onClick={() => { setResetMode(false); setResetSent(false); }}
              className="text-sm cursor-pointer bg-transparent border-none font-[inherit]"
              style={{ color: brandColor }}
            >
              Back to login
            </button>
          </div>
        )}

        {/* Magic link sent confirmation */}
        {magicLinkSent && !resetSent && (
          <div className="text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 mx-auto mb-4 flex items-center justify-center text-emerald-400">
              <Mail size={24} />
            </div>
            <p className="text-white font-medium mb-2">Check your email</p>
            <p className="text-sm text-[#71717A] mb-5">
              We sent a sign-in link to {email}
            </p>
            <button
              onClick={() => { setMagicLinkMode(false); setMagicLinkSent(false); }}
              className="text-sm cursor-pointer bg-transparent border-none font-[inherit]"
              style={{ color: brandColor }}
            >
              Back to login
            </button>
          </div>
        )}

        {/* Main login form */}
        {!resetSent && !magicLinkSent && (
          <>
            {/* Google SSO button */}
            {!resetMode && !magicLinkMode && (
              <div className="mb-5">
                <button
                  onClick={handleGoogleLogin}
                  disabled={googleLoading}
                  className="w-full flex items-center justify-center gap-3 py-3 px-4 rounded-lg border-none bg-white text-gray-800 font-medium text-sm cursor-pointer transition-opacity duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {googleLoading ? (
                    <div className="w-5 h-5 border-2 border-gray-300 border-t-gray-600 rounded-full animate-spin" />
                  ) : (
                    <svg width="20" height="20" viewBox="0 0 24 24">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4" />
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                    </svg>
                  )}
                  {googleLoading ? "Connecting..." : "Continue with Google"}
                </button>

                {/* Divider */}
                <div className="flex items-center gap-3 my-5">
                  <div className="flex-1 h-px bg-[rgba(255,255,255,0.06)]" />
                  <span className="text-[11px] text-[#71717A] uppercase tracking-wider">or</span>
                  <div className="flex-1 h-px bg-[rgba(255,255,255,0.06)]" />
                </div>
              </div>
            )}

            <form onSubmit={resetMode ? handleReset : magicLinkMode ? handleMagicLink : handleLogin}>
              {/* Email field */}
              <div className="mb-5">
                <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.co.za"
                  required
                  autoComplete="email"
                />
              </div>

              {/* Password field (only for standard login) */}
              {!resetMode && !magicLinkMode && (
                <div className="mb-5">
                  <label className="block text-sm font-medium text-[#A1A1AA] mb-2">
                    Password
                  </label>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="Enter your password"
                    required
                    autoComplete="current-password"
                  />
                </div>
              )}

              {/* Remember me / Forgot */}
              {!resetMode && !magicLinkMode && (
                <div className="flex justify-between items-center mb-6 text-[13px] text-[#A1A1AA]">
                  <label className="flex items-center gap-1.5 cursor-pointer">
                    <input type="checkbox" style={{ accentColor: brandColor }} /> Remember me
                  </label>
                  <button
                    type="button"
                    onClick={() => { setResetMode(true); setError(""); }}
                    className="bg-transparent border-none cursor-pointer text-[13px] font-[inherit]"
                    style={{ color: brandColor }}
                  >
                    Forgot password?
                  </button>
                </div>
              )}

              {/* Error message */}
              {error && (
                <p className="text-[13px] text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4">
                  {error}
                </p>
              )}

              {/* Submit button */}
              <button
                type="submit"
                disabled={loading}
                className="w-full py-3.5 rounded-lg border-none text-white font-semibold text-[15px] cursor-pointer transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
                style={{ background: brandColor }}
              >
                {loading
                  ? "Please wait..."
                  : resetMode
                  ? "Send Reset Link"
                  : magicLinkMode
                  ? "Send Sign-in Link"
                  : "Sign In"}
              </button>

              {/* Magic link option */}
              {!resetMode && !magicLinkMode && (
                <div className="text-center mt-3.5">
                  <button
                    type="button"
                    onClick={() => { setMagicLinkMode(true); setError(""); }}
                    className="bg-transparent border-none text-[#71717A] cursor-pointer text-[13px] font-[inherit] inline-flex items-center gap-1.5"
                  >
                    <Mail size={14} />
                    Sign in with email link instead
                  </button>
                </div>
              )}

              {/* Back to login from sub-modes */}
              {(resetMode || magicLinkMode) && (
                <div className="text-center mt-4">
                  <button
                    type="button"
                    onClick={() => { setResetMode(false); setMagicLinkMode(false); setError(""); }}
                    className="bg-transparent border-none cursor-pointer text-[13px] font-[inherit]"
                    style={{ color: brandColor }}
                  >
                    Back to login
                  </button>
                </div>
              )}

            </form>
          </>
        )}
      </div>

      {/* Trust signals */}
      <div className="flex items-center gap-6 mt-8 text-[12px] text-[#52525B]">
        <div className="flex items-center gap-1.5">
          <Lock size={13} />
          <span>256-bit encrypted</span>
        </div>
        <div className="flex items-center gap-1.5">
          <ShieldCheck size={13} />
          <span>POPIA compliant</span>
        </div>
      </div>

      {/* Legal links + back to site */}
      <div className="flex items-center gap-4 mt-6 text-[12px] text-[#52525B]">
        <Link href="/portal/legal/privacy" className="text-inherit no-underline hover:text-[#71717A]">
          Privacy
        </Link>
        <Link href="/portal/legal/terms" className="text-inherit no-underline hover:text-[#71717A]">
          Terms
        </Link>
        <a href="https://www.anyvisionmedia.com" className="text-inherit no-underline hover:text-[#71717A]">
          &larr; anyvisionmedia.com
        </a>
      </div>
    </div>
  );
}
