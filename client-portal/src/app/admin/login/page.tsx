"use client";

import { useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Shield, Lock } from "lucide-react";

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

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-lg relative animate-fade-in-up">
        {/* Logo */}
        <div className="text-center mb-10">
          <div className="inline-flex items-center gap-2.5 mb-4">
            <Shield size={28} className="text-[#6366F1]" />
            <span className="text-2xl font-bold text-white">
              AnyVision<span className="text-[#10B981]">.</span>
            </span>
          </div>
          <h1 className="text-2xl font-bold text-white">Admin Dashboard</h1>
          <p className="text-sm text-[#71717A] mt-2">Internal access only</p>
        </div>

        {/* Form */}
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

            {error && (
              <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button type="submit" variant="primary" loading={loading} className="w-full">
              Sign In
            </Button>
          </form>
        </div>
      </div>

      {/* Trust signal */}
      <div className="flex items-center gap-1.5 mt-8 text-[12px] text-[#52525B]">
        <Lock size={13} />
        <span>Secured connection</span>
      </div>
    </div>
  );
}
