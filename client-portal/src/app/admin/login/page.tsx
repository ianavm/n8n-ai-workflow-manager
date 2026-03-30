"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function AdminLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();
  const supabase = createClient();

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const { data, error: authError } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }

    const { data: adminUser } = await supabase
      .from("admin_users")
      .select("role")
      .eq("auth_user_id", data.user.id)
      .maybeSingle();

    if (adminUser) {
      router.push("/admin");
      router.refresh();
      return;
    }

    // Check if user is a financial adviser
    const { data: adviser } = await supabase
      .from("fa_advisers")
      .select("id, role")
      .eq("auth_user_id", data.user.id)
      .eq("active", true)
      .maybeSingle();

    if (adviser) {
      router.push("/admin/advisory/my-dashboard");
      router.refresh();
      return;
    }

    await supabase.auth.signOut();
    setError("This account does not have admin access");
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
                <linearGradient id="adminGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#6C63FF" />
                  <stop offset="100%" stopColor="#00D4AA" />
                </linearGradient>
              </defs>
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#adminGrad)" opacity="0.10" />
              <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#adminGrad)" strokeWidth="8" strokeLinejoin="round" />
              <circle cx="100" cy="100" r="42" fill="none" stroke="url(#adminGrad)" strokeWidth="5" opacity="0.5" />
              <path d="M100,52 L140,100 L100,92 Z" fill="url(#adminGrad)" />
              <path d="M100,108 L140,100 L100,148 Z" fill="url(#adminGrad)" />
              <path d="M100,52 L60,100 L100,92 Z" fill="url(#adminGrad)" />
              <path d="M100,108 L60,100 L100,148 Z" fill="url(#adminGrad)" />
              <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
              <circle cx="100" cy="100" r="16" fill="none" stroke="url(#adminGrad)" strokeWidth="2" opacity="0.4" />
              <circle cx="91" cy="91" r="5" fill="rgba(255,255,255,0.85)" />
            </svg>
            <span className="text-2xl font-bold text-white">
              AnyVision<span className="text-[#FF6D5A]">.</span>
            </span>
          </div>
          <h1 className="text-3xl font-bold text-white">Admin Dashboard</h1>
          <p className="text-base text-[#6B7280] mt-2">Internal access only</p>
        </div>

        {/* Form */}
        <div className="glass-card p-10 transition-shadow duration-300 focus-within:shadow-[0_0_30px_rgba(108,99,255,0.08)]">
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

            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" variant="coral" loading={loading} className="w-full">
              Sign In
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}
