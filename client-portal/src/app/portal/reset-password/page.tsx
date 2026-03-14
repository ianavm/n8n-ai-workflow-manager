"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
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

export default function ResetPasswordPage() {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [ready, setReady] = useState(false);
  const [success, setSuccess] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  useEffect(() => {
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") {
        setReady(true);
      }
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

    const allRulesPassed = PASSWORD_RULES.every((r) => r.test(password));
    if (!allRulesPassed) {
      setError("Password does not meet all requirements");
      return;
    }

    setLoading(true);

    const { error: updateError } = await supabase.auth.updateUser({
      password,
    });

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

      <div className="w-full max-w-md relative animate-fade-in-up">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <svg viewBox="0 0 200 200" width="40" height="40" xmlns="http://www.w3.org/2000/svg">
              <defs>
                <linearGradient id="resetGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#6C63FF" />
                  <stop offset="100%" stopColor="#00D4AA" />
                </linearGradient>
              </defs>
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#resetGrad)" opacity="0.10" />
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#resetGrad)" strokeWidth="8" strokeLinejoin="round" />
              <circle cx="100" cy="100" r="42" fill="none" stroke="url(#resetGrad)" strokeWidth="5" opacity="0.5" />
              <path d="M100,52 L140,100 L100,92 Z" fill="url(#resetGrad)" />
              <path d="M100,108 L140,100 L100,148 Z" fill="url(#resetGrad)" />
              <path d="M100,52 L60,100 L100,92 Z" fill="url(#resetGrad)" />
              <path d="M100,108 L60,100 L100,148 Z" fill="url(#resetGrad)" />
              <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
              <circle cx="100" cy="100" r="16" fill="none" stroke="url(#resetGrad)" strokeWidth="2" opacity="0.4" />
              <circle cx="91" cy="91" r="5" fill="rgba(255,255,255,0.85)" />
            </svg>
            <span className="text-xl font-bold text-white">
              AnyVision<span className="text-[#00D4AA]">.</span>
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Reset Password</h1>
          <p className="text-sm text-[#6B7280] mt-1">
            {ready ? "Enter your new password below" : "Processing your reset link..."}
          </p>
        </div>

        {/* Form */}
        <div className="glass-card p-8 transition-shadow duration-300 focus-within:shadow-[0_0_30px_rgba(108,99,255,0.08)]">
          {success ? (
            <div className="text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/10 border border-emerald-500/20 mx-auto flex items-center justify-center text-[#00D4AA]">
                <Check size={24} />
              </div>
              <p className="text-white font-medium">Password updated!</p>
              <p className="text-sm text-[#6B7280]">
                Redirecting you to the portal...
              </p>
            </div>
          ) : ready ? (
            <form onSubmit={handleReset} className="space-y-5">
              <div className="relative">
                <Input
                  label="New Password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter new password"
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

              <div className="relative">
                <Input
                  label="Confirm New Password"
                  type={showConfirm ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
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

              {error && (
                <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              <Button type="submit" variant="coral" loading={loading} className="w-full">
                Update Password
              </Button>
            </form>
          ) : (
            <div className="text-center space-y-4">
              <p className="text-sm text-[#6B7280]">
                This page is for password reset links sent via email.
              </p>
              <p className="text-sm text-[#6B7280]">
                Need to reset your password?
              </p>
              <a href="/portal/login">
                <Button variant="ghost">Go to Login</Button>
              </a>
            </div>
          )}
        </div>

        {/* Back to main site */}
        <p className="text-center text-xs text-[#6B7280] mt-6">
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
