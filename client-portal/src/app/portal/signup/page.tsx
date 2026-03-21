"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Check, Eye, EyeOff, ArrowRight, Shield, Zap, BarChart3 } from "lucide-react";

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8, label: "At least 8 characters" },
  { test: (p: string) => /[A-Z]/.test(p), label: "One uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p), label: "One lowercase letter" },
  { test: (p: string) => /[0-9]/.test(p), label: "One number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p), label: "One special character" },
];

const FEATURES = [
  { icon: Zap, text: "AI-powered workflow automation" },
  { icon: BarChart3, text: "Real-time analytics dashboard" },
  { icon: Shield, text: "Enterprise-grade security" },
];

export default function SignupPage() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  async function handleSignup(e: React.FormEvent) {
    e.preventDefault();
    setError("");

    if (!firstName.trim() || !lastName.trim()) {
      setError("First name and last name are required");
      return;
    }

    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }

    const allRulesPassed = PASSWORD_RULES.every((r) => r.test(password));
    if (!allRulesPassed) {
      setError("Password does not meet all requirements");
      return;
    }

    setLoading(true);

    try {
      const res = await fetch("/api/auth/signup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          password,
          first_name: firstName.trim(),
          last_name: lastName.trim(),
          company_name: companyName.trim() || undefined,
          phone_number: phoneNumber.trim() || undefined,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        setError(data.error || "Failed to create account");
        setLoading(false);
        return;
      }

      setSuccess(true);
    } catch {
      setError("Network error. Please try again.");
    }
    setLoading(false);
  }

  const passedCount = PASSWORD_RULES.filter((r) => r.test(password)).length;
  const strengthPercent = (passedCount / PASSWORD_RULES.length) * 100;

  return (
    <div className="min-h-screen flex">
      {/* Left panel - branding (hidden on mobile) */}
      <div className="hidden lg:flex lg:w-[480px] xl:w-[520px] flex-col justify-between p-12 relative overflow-hidden"
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
          <h2 className="text-3xl font-bold text-white leading-tight mb-4">
            Automate your business with <span style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)", WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>intelligent AI agents</span>
          </h2>
          <p className="text-[#8B95A9] text-base leading-relaxed mb-10">
            Join forward-thinking South African businesses using AI to streamline operations, boost revenue, and reduce manual work.
          </p>

          <div className="space-y-5">
            {FEATURES.map(({ icon: Icon, text }) => (
              <div key={text} className="flex items-center gap-4">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ background: "rgba(108, 99, 255, 0.1)", border: "1px solid rgba(108, 99, 255, 0.2)" }}>
                  <Icon size={18} className="text-[#6C63FF]" />
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
      <div className="flex-1 flex items-center justify-center px-6 py-12 sm:px-12 relative">
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
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-white mb-2">Create your account</h1>
            <p className="text-sm text-[#8B95A9]">
              Start your 30-day free trial. No credit card required.
            </p>
          </div>

          {/* Card */}
          <div className="glass-card-static p-8 sm:p-10">
            {success ? (
              <div className="text-center py-6 space-y-5">
                <div className="w-16 h-16 rounded-2xl mx-auto flex items-center justify-center"
                  style={{ background: "rgba(0, 212, 170, 0.1)", border: "1px solid rgba(0, 212, 170, 0.2)" }}>
                  <Check size={28} className="text-[#00D4AA]" />
                </div>
                <div>
                  <p className="text-xl font-semibold text-white mb-2">Welcome aboard!</p>
                  <p className="text-sm text-[#8B95A9] leading-relaxed">
                    We&apos;ve sent a confirmation email to<br />
                    <span className="text-[#B0B8C8] font-medium">{email}</span>
                  </p>
                </div>
                <div className="pt-2 space-y-3">
                  <a href="/portal/login" className="block">
                    <Button variant="coral" className="w-full" size="lg">
                      Sign In to Your Portal
                      <ArrowRight size={16} className="ml-1" />
                    </Button>
                  </a>
                  <p className="text-xs text-[#6B7280]">
                    Your 30-day free trial is active
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSignup} className="space-y-5">
                {/* Name row */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="firstName" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                      First Name
                    </label>
                    <input
                      id="firstName"
                      type="text"
                      value={firstName}
                      onChange={(e) => setFirstName(e.target.value)}
                      placeholder="John"
                      required
                      autoComplete="given-name"
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label htmlFor="lastName" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                      Last Name
                    </label>
                    <input
                      id="lastName"
                      type="text"
                      value={lastName}
                      onChange={(e) => setLastName(e.target.value)}
                      placeholder="Smith"
                      required
                      autoComplete="family-name"
                      className="w-full"
                    />
                  </div>
                </div>

                {/* Email */}
                <div>
                  <label htmlFor="email" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
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

                {/* Password */}
                <div>
                  <label htmlFor="password" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                    Password
                  </label>
                  <div className="relative">
                    <input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      placeholder="Create a strong password"
                      required
                      autoComplete="new-password"
                      className="w-full pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
                      tabIndex={-1}
                    >
                      {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>

                  {/* Strength bar */}
                  {password && (
                    <div className="mt-3 space-y-2">
                      <div className="flex gap-1">
                        {PASSWORD_RULES.map((rule, i) => (
                          <div key={i} className="h-1 flex-1 rounded-full transition-all duration-300"
                            style={{
                              background: i < passedCount
                                ? passedCount <= 2 ? "#EF4444"
                                : passedCount <= 4 ? "#F59E0B"
                                : "#00D4AA"
                                : "rgba(255,255,255,0.06)"
                            }} />
                        ))}
                      </div>
                      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
                        {PASSWORD_RULES.map((rule) => {
                          const passed = rule.test(password);
                          return (
                            <div key={rule.label} className="flex items-center gap-1.5">
                              <div className={`w-3 h-3 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-200 ${passed ? "bg-[#00D4AA]/20" : ""}`}>
                                {passed && <Check size={8} className="text-[#00D4AA]" />}
                              </div>
                              <span className={`text-[11px] ${passed ? "text-[#8B95A9]" : "text-[#4B5563]"}`}>
                                {rule.label}
                              </span>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}
                </div>

                {/* Confirm Password */}
                <div>
                  <label htmlFor="confirmPassword" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                    Confirm Password
                  </label>
                  <div className="relative">
                    <input
                      id="confirmPassword"
                      type={showConfirm ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm your password"
                      required
                      autoComplete="new-password"
                      className={`w-full pr-10 ${confirmPassword && password !== confirmPassword ? "border-red-500/50 focus:border-red-500" : ""}`}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm(!showConfirm)}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
                      tabIndex={-1}
                    >
                      {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                    </button>
                  </div>
                  {confirmPassword && password !== confirmPassword && (
                    <p className="text-xs text-red-400 mt-1.5">Passwords do not match</p>
                  )}
                </div>

                {/* Optional fields — collapsible row */}
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label htmlFor="companyName" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                      Company <span className="text-[#4B5563] normal-case tracking-normal">(optional)</span>
                    </label>
                    <input
                      id="companyName"
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="Acme Corp"
                      autoComplete="organization"
                      className="w-full"
                    />
                  </div>
                  <div>
                    <label htmlFor="phoneNumber" className="block text-xs font-medium text-[#8B95A9] mb-1.5 uppercase tracking-wider">
                      Phone <span className="text-[#4B5563] normal-case tracking-normal">(optional)</span>
                    </label>
                    <input
                      id="phoneNumber"
                      type="tel"
                      value={phoneNumber}
                      onChange={(e) => setPhoneNumber(e.target.value)}
                      placeholder="+27 82 123 4567"
                      autoComplete="tel"
                      className="w-full"
                    />
                  </div>
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

                {/* Terms */}
                <p className="text-[11px] text-[#4B5563] text-center leading-relaxed">
                  By creating an account, you agree to our{" "}
                  <a href="https://www.anyvisionmedia.com/terms" className="text-[#6B7280] hover:text-[#B0B8C8] underline underline-offset-2 transition-colors">
                    Terms of Service
                  </a>{" "}
                  and{" "}
                  <a href="https://www.anyvisionmedia.com/refund-policy" className="text-[#6B7280] hover:text-[#B0B8C8] underline underline-offset-2 transition-colors">
                    Privacy Policy
                  </a>
                </p>
              </form>
            )}
          </div>

          {/* Footer links */}
          <div className="flex items-center justify-between mt-6 px-1">
            <a
              href="/portal/login"
              className="text-sm text-[#6C63FF] hover:text-[#00D4AA] transition-colors font-medium"
            >
              Already have an account? Sign in
            </a>
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
