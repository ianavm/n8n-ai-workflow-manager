"use client";

import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Check, Eye, EyeOff } from "lucide-react";

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8, label: "At least 8 characters" },
  { test: (p: string) => /[A-Z]/.test(p), label: "One uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p), label: "One lowercase letter" },
  { test: (p: string) => /[0-9]/.test(p), label: "One number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p), label: "One special character" },
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

    // Client-side validation
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

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden">
      {/* Animated gradient orbs */}
      <div
        className="absolute top-1/4 -left-32 w-96 h-96 rounded-full opacity-30 blur-3xl pointer-events-none animate-float"
        style={{ background: "radial-gradient(circle, rgba(108,99,255,0.3), transparent 70%)" }}
      />
      <div
        className="absolute bottom-1/4 -right-32 w-80 h-80 rounded-full opacity-25 blur-3xl pointer-events-none animate-float"
        style={{ background: "radial-gradient(circle, rgba(255,109,90,0.25), transparent 70%)", animationDelay: "2s", animationDirection: "reverse" }}
      />
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[500px] h-[500px] rounded-full opacity-10 blur-3xl pointer-events-none"
        style={{ background: "radial-gradient(circle, rgba(0,212,170,0.2), transparent 70%)" }}
      />

      <div className="w-full max-w-lg relative animate-fade-in-up">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-3 mb-5">
            <svg viewBox="0 0 200 200" width="44" height="44" xmlns="http://www.w3.org/2000/svg">
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
            <span className="text-2xl font-bold text-white">
              AnyVision<span className="text-[#FF6D5A]">.</span>
            </span>
          </div>
          <h1 className="text-3xl font-bold text-white">Create Account</h1>
          <p className="text-base text-[#6B7280] mt-2">
            Get started with your AI automation portal
          </p>
        </div>

        {/* Form */}
        <div className="glass-card p-10 transition-shadow duration-300 focus-within:shadow-[0_0_30px_rgba(108,99,255,0.08)]">
          {success ? (
            <div className="text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 mx-auto flex items-center justify-center text-[#00D4AA]">
                <Check size={24} />
              </div>
              <p className="text-white font-medium">Account created!</p>
              <p className="text-sm text-[#6B7280]">
                Check your email at <span className="text-[#B0B8C8]">{email}</span> to verify your account, then sign in.
              </p>
              <a href="/portal/login">
                <Button variant="coral" className="w-full mt-2">
                  Go to Login
                </Button>
              </a>
            </div>
          ) : (
            <form onSubmit={handleSignup} className="space-y-5">
              {/* Name fields */}
              <div className="grid grid-cols-2 gap-4">
                <Input
                  label="First Name"
                  type="text"
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  placeholder="John"
                  required
                  autoComplete="given-name"
                />
                <Input
                  label="Last Name"
                  type="text"
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  placeholder="Doe"
                  required
                  autoComplete="family-name"
                />
              </div>

              <Input
                label="Email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@company.com"
                required
                autoComplete="email"
              />

              {/* Password with toggle */}
              <div className="relative">
                <Input
                  label="Password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Create a strong password"
                  required
                  autoComplete="new-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-[34px] text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {/* Password strength indicator */}
              {password && (
                <div className="space-y-1.5 px-1">
                  {PASSWORD_RULES.map((rule) => {
                    const passed = rule.test(password);
                    return (
                      <div key={rule.label} className="flex items-center gap-2 text-xs">
                        <div className={`w-3.5 h-3.5 rounded-full flex items-center justify-center ${passed ? "bg-emerald-500/20 text-[#00D4AA]" : "bg-[rgba(255,255,255,0.05)] text-[#6B7280]"}`}>
                          {passed && <Check size={10} />}
                        </div>
                        <span className={passed ? "text-[#B0B8C8]" : "text-[#6B7280]"}>
                          {rule.label}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Confirm password with toggle */}
              <div className="relative">
                <Input
                  label="Confirm Password"
                  type={showConfirm ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm your password"
                  required
                  autoComplete="new-password"
                  error={confirmPassword && password !== confirmPassword ? "Passwords do not match" : undefined}
                />
                <button
                  type="button"
                  onClick={() => setShowConfirm(!showConfirm)}
                  className="absolute right-3 top-[34px] text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
                  tabIndex={-1}
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>

              {/* Optional fields */}
              <Input
                label="Company Name"
                type="text"
                value={companyName}
                onChange={(e) => setCompanyName(e.target.value)}
                placeholder="Optional"
                autoComplete="organization"
              />

              <Input
                label="Phone Number"
                type="tel"
                value={phoneNumber}
                onChange={(e) => setPhoneNumber(e.target.value)}
                placeholder="Optional"
                autoComplete="tel"
              />

              {error && (
                <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <Button type="submit" variant="coral" loading={loading} className="w-full">
                Create Account
              </Button>

              <div className="text-center pt-2">
                <a
                  href="/portal/login"
                  className="text-sm text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
                >
                  Already have an account? Sign in
                </a>
              </div>
            </form>
          )}
        </div>

        {/* Back to main site */}
        <p className="text-center text-sm text-[#6B7280] mt-8">
          <a
            href="https://www.anyvisionmedia.com"
            className="hover:text-[#B0B8C8] transition-colors"
          >
            &larr; Back to anyvisionmedia.com
          </a>
        </p>
      </div>
    </div>
  );
}
