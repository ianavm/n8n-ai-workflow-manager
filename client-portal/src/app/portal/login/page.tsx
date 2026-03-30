"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Check } from "lucide-react";

export default function PortalLoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [resetMode, setResetMode] = useState(false);
  const [resetSent, setResetSent] = useState(false);
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
      setError("Invalid email or password");
      setLoading(false);
      return;
    }

    // Server-side role check (uses service role to bypass RLS)
    try {
      const res = await fetch("/api/auth/check-role");
      if (!res.ok) {
        // API error — fall back to portal home
        window.location.href = "/portal";
        return;
      }
      const { redirect } = await res.json();
      const target = redirect || "/portal";
      // Prevent redirect loop back to the same login page
      if (target === "/portal/login") {
        setError("Account not found. Please contact support.");
        setLoading(false);
        return;
      }
      window.location.href = target;
    } catch {
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

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        position: "relative",
        backgroundImage: "radial-gradient(rgba(255,255,255,0.03) 1px, transparent 1px)",
        backgroundSize: "32px 32px",
        overflow: "hidden",
        padding: "0 16px",
      }}
    >
      {/* Login blobs -- V1 preview exact values */}
      <div className="login-blob lb1" />
      <div className="login-blob lb2" />

      {/* Login card */}
      <div
        className="animate-fade-in-up"
        style={{
          width: "100%",
          maxWidth: "480px",
          padding: "48px",
          background: "rgba(255,255,255,0.05)",
          border: "1px solid rgba(255,255,255,0.08)",
          borderRadius: "20px",
          backdropFilter: "blur(20px)",
          WebkitBackdropFilter: "blur(20px)",
          position: "relative",
          zIndex: 1,
        }}
      >
        {/* Logo */}
        <div style={{ textAlign: "center", marginBottom: "32px" }}>
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ margin: "0 auto" }}>
            <defs>
              <linearGradient id="lgLogin" x1="0" y1="0" x2="48" y2="48">
                <stop stopColor="#6C63FF" />
                <stop offset="1" stopColor="#00D4AA" />
              </linearGradient>
            </defs>
            <circle cx="24" cy="24" r="22" stroke="url(#lgLogin)" strokeWidth="2" fill="none" />
            <circle cx="24" cy="24" r="14" stroke="url(#lgLogin)" strokeWidth="1.5" fill="none" opacity="0.5" />
            <circle cx="24" cy="24" r="5" fill="url(#lgLogin)" />
            <circle cx="24" cy="6" r="3" fill="#6C63FF" />
            <circle cx="42" cy="24" r="3" fill="#00D4AA" />
            <circle cx="24" cy="42" r="3" fill="#FF6D5A" />
          </svg>
          <div
            style={{
              fontSize: "26px",
              fontWeight: 700,
              letterSpacing: "3px",
              background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
              marginTop: "16px",
            }}
          >
            ANYVISION MEDIA
          </div>
          <div style={{ fontSize: "14px", color: "#6B7280", marginTop: "6px" }}>
            {resetMode ? "Reset your password" : "AI Workflow Command Center"}
          </div>
        </div>

        {resetSent ? (
          <div style={{ textAlign: "center" }}>
            <div
              style={{
                width: "48px",
                height: "48px",
                borderRadius: "50%",
                background: "rgba(16,185,129,0.1)",
                border: "1px solid rgba(16,185,129,0.2)",
                margin: "0 auto 16px auto",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#00D4AA",
              }}
            >
              <Check size={24} />
            </div>
            <p style={{ color: "#fff", fontWeight: 500, marginBottom: "8px" }}>Check your email</p>
            <p style={{ fontSize: "14px", color: "#6B7280", marginBottom: "20px" }}>
              We sent a password reset link to {email}
            </p>
            <button
              onClick={() => { setResetMode(false); setResetSent(false); }}
              style={{
                background: "none",
                border: "none",
                color: "#6C63FF",
                cursor: "pointer",
                fontSize: "13px",
                fontFamily: "inherit",
              }}
            >
              Back to login
            </button>
          </div>
        ) : (
          <form onSubmit={resetMode ? handleReset : handleLogin}>
            {/* Email field */}
            <div style={{ marginBottom: "22px" }}>
              <label style={{ display: "block", fontSize: "14px", fontWeight: 500, color: "#B0B8C8", marginBottom: "8px" }}>
                Email Address
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ian@anyvisionmedia.com"
                required
                autoComplete="email"
                style={{
                  width: "100%",
                  padding: "14px 18px",
                  borderRadius: "10px",
                  border: "1px solid rgba(255,255,255,0.08)",
                  background: "rgba(255,255,255,0.04)",
                  color: "#fff",
                  fontFamily: "inherit",
                  fontSize: "14px",
                  outline: "none",
                }}
              />
            </div>

            {/* Password field */}
            {!resetMode && (
              <div style={{ marginBottom: "22px" }}>
                <label style={{ display: "block", fontSize: "14px", fontWeight: 500, color: "#B0B8C8", marginBottom: "8px" }}>
                  Password
                </label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  style={{
                    width: "100%",
                    padding: "14px 18px",
                    borderRadius: "10px",
                    border: "1px solid rgba(255,255,255,0.08)",
                    background: "rgba(255,255,255,0.04)",
                    color: "#fff",
                    fontFamily: "inherit",
                    fontSize: "14px",
                    outline: "none",
                  }}
                />
              </div>
            )}

            {/* Remember me / Forgot */}
            {!resetMode && (
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  marginBottom: "24px",
                  fontSize: "13px",
                  color: "#B0B8C8",
                }}
              >
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input type="checkbox" style={{ accentColor: "#6C63FF" }} /> Remember me
                </label>
                <button
                  type="button"
                  onClick={() => { setResetMode(true); setError(""); }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#6C63FF",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontFamily: "inherit",
                    textDecoration: "none",
                  }}
                >
                  Forgot password?
                </button>
              </div>
            )}

            {/* Error message */}
            {error && (
              <p style={{
                fontSize: "13px",
                color: "#EF4444",
                background: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.2)",
                borderRadius: "10px",
                padding: "8px 12px",
                marginBottom: "18px",
              }}>
                {error}
              </p>
            )}

            {/* Submit button -- gradient CTA, full width */}
            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "14px 32px",
                borderRadius: "12px",
                border: "none",
                background: "linear-gradient(135deg, #6C63FF, #00D4AA)",
                color: "#fff",
                fontFamily: "inherit",
                fontSize: "15px",
                fontWeight: 600,
                cursor: loading ? "not-allowed" : "pointer",
                opacity: loading ? 0.6 : 1,
                transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
              }}
            >
              {loading ? "Signing in..." : resetMode ? "Send Reset Link" : "Sign In"}
            </button>

            {/* Social login removed -- no OAuth providers configured */}

            {resetMode && (
              <div style={{ textAlign: "center", marginTop: "16px" }}>
                <button
                  type="button"
                  onClick={() => { setResetMode(false); setError(""); }}
                  style={{
                    background: "none",
                    border: "none",
                    color: "#6C63FF",
                    cursor: "pointer",
                    fontSize: "13px",
                    fontFamily: "inherit",
                  }}
                >
                  Back to login
                </button>
              </div>
            )}

            {/* Create account link */}
            {!resetMode && (
              <div style={{ textAlign: "center", marginTop: "16px" }}>
                <Link
                  href="/portal/signup"
                  style={{ fontSize: "13px", color: "#6B7280", textDecoration: "none" }}
                >
                  Don&apos;t have an account? <span style={{ color: "#6C63FF" }}>Sign up</span>
                </Link>
              </div>
            )}
          </form>
        )}
      </div>

      {/* Back to main site */}
      <p style={{
        position: "absolute",
        bottom: "24px",
        left: "50%",
        transform: "translateX(-50%)",
        fontSize: "12px",
        color: "#6B7280",
        zIndex: 1,
      }}>
        <a href="https://www.anyvisionmedia.com" style={{ color: "inherit", textDecoration: "none" }}>
          &larr; Back to anyvisionmedia.com
        </a>
      </p>
    </div>
  );
}
