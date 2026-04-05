"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { ArrowRight, Shield, Zap, BarChart3, Mail } from "lucide-react";

const FEATURES = [
  { icon: Zap, text: "AI-powered workflow automation" },
  { icon: BarChart3, text: "Real-time analytics dashboard" },
  { icon: Shield, text: "Enterprise-grade security" },
];

type SignupMode = "choose" | "email" | "magic_link_sent";

export default function SignupPage() {
  const [mode, setMode] = useState<SignupMode>("choose");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);

  const supabase = createClient();

  async function handleGoogleSignup() {
    if (!consentGiven) {
      setError("Please agree to the terms and data processing consent to continue.");
      return;
    }
    setError("");
    setGoogleLoading(true);
    const { error: oauthError } = await supabase.auth.signInWithOAuth({
      provider: "google",
      options: {
        redirectTo: `${window.location.origin}/portal/auth/callback?onboarding=true`,
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

  async function handleEmailSignup(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!consentGiven) {
      setError("Please agree to the terms and data processing consent to continue.");
      return;
    }

    if (!fullName.trim()) {
      setError("Full name is required");
      return;
    }

    if (!email.trim()) {
      setError("Email is required");
      return;
    }

    if (!companyName.trim()) {
      setError("Company name is required");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          full_name: fullName.trim(),
          company_name: companyName.trim(),
          signup_method: "magic_link",
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Failed to create account");
        setLoading(false);
        return;
      }

      // Server-side inviteUserByEmail already sent the magic link email
      setMode("magic_link_sent");
    } catch {
      setError("Network error. Please try again.");
    }
    setLoading(false);
  }

  return (
    <div className="h-screen flex overflow-hidden">
      {/* Left panel - branding (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-[440px] xl:w-[480px] flex-col justify-between p-8 xl:p-10 relative overflow-hidden"
        style={{ background: "linear-gradient(135deg, #0D1326 0%, #131B36 50%, #0A0F1C 100%)" }}>
        {/* Decorative gradient orbs */}
        <div className="absolute top-20 -left-20 w-80 h-80 rounded-full opacity-20 blur-3xl pointer-events-none"
          style={{ background: "radial-gradient(circle, #6C63FF, transparent 70%)" }} />
        <div className="absolute bottom-32 -right-16 w-64 h-64 rounded-full opacity-15 blur-3xl pointer-events-none"
          style={{ background: "radial-gradient(circle, #00D4AA, transparent 70%)" }} />

        {/* Logo */}
        <div>
          <div className="flex items-center gap-3 mb-2">
            <svg viewBox="0 0 200 200" width="36" height="36" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="signupGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#6C63FF" />
                  <stop offset="100%" stopColor="#00D4AA" />
                </linearGradient>
              </defs>
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#signupGrad)" opacity="0.10" />
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#signupGrad)" strokeWidth="8" strokeLinejoin="round" />
              <circle cx="100" cy="100" r="42" fill="none" stroke="url(#signupGrad)" strokeWidth="5" opacity="0.5" />
              <path d="M100,52 L140,100 L100,92 Z" fill="url(#signupGrad)" />
              <path d="M100,108 L140,100 L100,148 Z" fill="url(#signupGrad)" />
              <path d="M100,52 L60,100 L100,92 Z" fill="url(#signupGrad)" />
              <path d="M100,108 L60,100 L100,148 Z" fill="url(#signupGrad)" />
              <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
              <circle cx="100" cy="100" r="16" fill="none" stroke="url(#signupGrad)" strokeWidth="2" opacity="0.4" />
              <circle cx="91" cy="91" r="5" fill="rgba(255,255,255,0.85)" />
            </svg>
            <span className="text-xl font-bold text-white">
              AnyVision<span className="text-[#FF6D5A]">.</span>
            </span>
          </div>
        </div>

        {/* Value prop */}
        <div className="relative z-10">
          <h2 className="text-2xl xl:text-3xl font-bold text-white leading-tight mb-3">
            Automate your business with <span style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>intelligent AI agents</span>
          </h2>
          <p className="text-[#8B95A9] text-sm leading-relaxed mb-6">
            Join forward-thinking South African businesses using AI to streamline operations, boost revenue, and reduce manual work.
          </p>

          <div className="space-y-3">
            {FEATURES.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(108, 99, 255, 0.1)", border: "1px solid rgba(108, 99, 255, 0.2)" }}>
                  <Icon size={16} className="text-[#6C63FF]" />
                </div>
                <span className="text-[#B0B8C8] text-sm">{text}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Social proof */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-3">
            <div className="flex -space-x-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="w-8 h-8 rounded-full border-2 border-[#0D1326] flex items-center justify-center text-[10px] font-semibold text-white"
                  style={{ background: `linear-gradient(135deg, ${["#6C63FF", "#00D4AA", "#FF6D5A", "#3B82F6"][i - 1]}, ${["#00D4AA", "#6C63FF", "#FF8A6B", "#6366F1"][i - 1]})` }}>
                  {["IM", "JD", "NM", "AS"][i - 1]}
                </div>
              ))}
            </div>
            <span className="text-[#8B95A9] text-sm">Trusted by 50+ businesses</span>
          </div>
          <p className="text-[#6B7280] text-xs">
            30-day free trial. No credit card required.
          </p>
        </div>
      </div>

      {/* Right panel - form */}
      <div className="flex-1 flex items-center justify-center px-6 py-6 sm:px-12 relative overflow-y-auto">
        {/* Subtle background texture */}
        <div className="absolute inset-0 opacity-[0.02] pointer-events-none"
          style={{ backgroundImage: "radial-gradient(circle at 1px 1px, white 1px, transparent 0)", backgroundSize: "32px 32px" }} />

        <div className="w-full max-w-[460px] relative">
          {/* Mobile logo (hidden on desktop) */}
          <div className="lg:hidden text-center mb-8">
            <div className="inline-flex items-center gap-3 mb-4">
              <svg viewBox="0 0 200 200" width="36" height="36" xmlns="http://www.w3.org/2000/svg">
                <defs>
                  <linearGradient id="signupGradMobile" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stopColor="#6C63FF" />
                    <stop offset="100%" stopColor="#00D4AA" />
                  </linearGradient>
                </defs>
                <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#signupGradMobile)" opacity="0.10" />
                <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#signupGradMobile)" strokeWidth="8" strokeLinejoin="round" />
                <circle cx="100" cy="100" r="42" fill="none" stroke="url(#signupGradMobile)" strokeWidth="5" opacity="0.5" />
                <path d="M100,52 L140,100 L100,92 Z" fill="url(#signupGradMobile)" />
                <path d="M100,108 L140,100 L100,148 Z" fill="url(#signupGradMobile)" />
                <path d="M100,52 L60,100 L100,92 Z" fill="url(#signupGradMobile)" />
                <path d="M100,108 L60,100 L100,148 Z" fill="url(#signupGradMobile)" />
                <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
                <circle cx="100" cy="100" r="16" fill="none" stroke="url(#signupGradMobile)" strokeWidth="2" opacity="0.4" />
                <circle cx="91" cy="91" r="5" fill="rgba(255,255,255,0.85)" />
              </svg>
              <span className="text-xl font-bold text-white">
                AnyVision<span className="text-[#FF6D5A]">.</span>
              </span>
            </div>
          </div>

          {/* Header */}
          <div className="mb-5">
            <h1 className="text-2xl font-bold text-white mb-1">
              {mode === "email" ? "Create your account" : "Get started in seconds"}
            </h1>
            <p className="text-sm text-[#8B95A9]">
              Start your 30-day free trial. No credit card required.
            </p>
          </div>

          {/* Card */}
          <div className="glass-card-static p-6 sm:p-8">
            {/* Magic link sent confirmation */}
            {mode === "magic_link_sent" && (
              <div className="text-center py-6 space-y-5">
                <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center"
                  style={{ background: "rgba(0, 212, 170, 0.1)", border: "1px solid rgba(0, 212, 170, 0.2)" }}>
                  <Mail size={28} className="text-[#00D4AA]" />
                </div>
                <div>
                  <p className="text-xl font-semibold text-white mb-2">Check your email</p>
                  <p className="text-sm text-[#8B95A9] leading-relaxed">
                    We sent a sign-in link to<br />
                    <span className="text-[#B0B8C8] font-medium">{email}</span>
                  </p>
                </div>
                <div className="pt-2 space-y-3">
                  <p className="text-xs text-[#6B7280]">
                    Click the link in your email to access your portal. Your 30-day free trial is active.
                  </p>
                  <button
                    onClick={() => { setMode("choose"); setError(""); }}
                    className="text-sm text-[#6C63FF] hover:text-[#00D4AA] transition-colors font-medium"
                  >
                    Use a different email
                  </button>
                </div>
              </div>
            )}

            {/* Initial choice: Google SSO or email */}
            {mode === "choose" && (
              <div className="space-y-4">
                {/* Google SSO - Primary CTA */}
                <button
                  onClick={handleGoogleSignup}
                  disabled={googleLoading}
                  className="w-full flex items-center justify-center gap-3 px-4 py-3.5 rounded-xl font-medium text-[15px] transition-all duration-200 hover:brightness-110 disabled:opacity-60 disabled:cursor-not-allowed"
                  style={{
                    background: "rgba(255,255,255,0.95)",
                    color: "#1f2937",
                  }}
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
                <div className="flex items-center gap-3">
                  <div className="flex-1 h-px bg-white/[0.06]" />
                  <span className="text-xs text-[#6B7280] uppercase tracking-wider">or</span>
                  <div className="flex-1 h-px bg-white/[0.06]" />
                </div>

                {/* Email signup button */}
                <button
                  onClick={() => setMode("email")}
                  className="w-full flex items-center justify-center gap-2 px-4 py-3.5 rounded-xl font-medium text-sm transition-all duration-200 hover:border-[#6C63FF]/40"
                  style={{
                    background: "rgba(255,255,255,0.04)",
                    border: "1px solid rgba(255,255,255,0.10)",
                    color: "#B0B8C8",
                  }}
                >
                  <Mail size={18} />
                  Sign up with email
                </button>

                {/* Error */}
                {error && (
                  <div className="flex items-start gap-2 text-sm text-red-400 bg-red-500/5 border border-red-500/15 rounded-xl px-4 py-3">
                    <span className="flex-shrink-0 mt-0.5">!</span>
                    <span>{error}</span>
                  </div>
                )}

                {/* POPIA consent */}
                <label className="flex items-start gap-2.5 pt-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={consentGiven}
                    onChange={(e) => setConsentGiven(e.target.checked)}
                    className="mt-0.5 w-4 h-4 rounded accent-[#6C63FF] flex-shrink-0"
                  />
                  <span className="text-[11px] text-[#4B5563] leading-relaxed">
                    I agree to the{" "}
                    <a href="https://www.anyvisionmedia.com/terms" className="text-[#6B7280] hover:text-[#B0B8C8] underline underline-offset-2 transition-colors">
                      Terms of Service
                    </a>{" "}
                    and{" "}
                    <a href="https://www.anyvisionmedia.com/refund-policy" className="text-[#6B7280] hover:text-[#B0B8C8] underline underline-offset-2 transition-colors">
                      Privacy Policy
                    </a>
                    , and consent to the processing of my personal data in accordance with POPIA.
                  </span>
                </label>
              </div>
            )}

            {/* Email form - 3 fields only */}
            {mode === "email" && (
              <form onSubmit={handleEmailSignup} className="space-y-3.5">
                {/* Full Name */}
                <div>
                  <label htmlFor="fullName" className="block text-xs font-medium text-[#8B95A9] mb-1 uppercase tracking-wider">
                    Full Name
                  </label>
                  <input
                    id="fullName"
                    type="text"
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="John Smith"
                    required
                    autoComplete="name"
                    autoFocus
                    className="w-full"
                  />
                </div>

                {/* Email */}
                <div>
                  <label htmlFor="email" className="block text-xs font-medium text-[#8B95A9] mb-1 uppercase tracking-wider">
                    Work Email
                  </label>
                  <input
                    id="email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="john@company.co.za"
                    required
                    autoComplete="email"
                    className="w-full"
                  />
                </div>

                {/* Company Name */}
                <div>
                  <label htmlFor="companyName" className="block text-xs font-medium text-[#8B95A9] mb-1 uppercase tracking-wider">
                    Company Name
                  </label>
                  <input
                    id="companyName"
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="Acme Corp"
                    required
                    autoComplete="organization"
                    className="w-full"
                  />
                </div>

                {/* Error */}
                {error && (
                  <div className="flex items-start gap-2 text-sm text-red-400 bg-red-500/5 border border-red-500/15 rounded-xl px-4 py-3">
                    <span className="flex-shrink-0 mt-0.5">!</span>
                    <span>{error}</span>
                  </div>
                )}

                {/* Submit */}
                <Button type="submit" variant="coral" loading={loading} className="w-full" size="lg">
                  {loading ? "Creating account..." : "Get Started"}
                  {!loading && <ArrowRight size={16} className="ml-1" />}
                </Button>

                {/* Info text */}
                <p className="text-[11px] text-[#4B5563] text-center leading-relaxed">
                  We&apos;ll send you a magic link to sign in — no password needed.
                </p>

                {/* Back to options */}
                <button
                  type="button"
                  onClick={() => { setMode("choose"); setError(""); }}
                  className="w-full text-center text-sm text-[#6C63FF] hover:text-[#00D4AA] transition-colors font-medium pt-1"
                >
                  Back to sign up options
                </button>
              </form>
            )}
          </div>

          {/* Footer links */}
          <div className="flex items-center justify-between mt-4 px-1">
            <Link
              href="/portal/login"
              className="text-sm text-[#6C63FF] hover:text-[#00D4AA] transition-colors font-medium"
            >
              Already have an account? Sign in
            </Link>
            <a
              href="https://www.anyvisionmedia.com"
              className="text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
            >
              anyvisionmedia.com
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
