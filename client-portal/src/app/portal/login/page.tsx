"use client";

import { useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Check, Mail } from "lucide-react";

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
  const supabase = createClient();

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

    // Server-side role check (uses service role to bypass RLS)
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
      {/* Login blobs */}
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
            {resetMode ? "Reset your password" : magicLinkMode ? "Sign in with email link" : "AI Workflow Command Center"}
          </div>
        </div>

        {/* Reset sent confirmation */}
        {resetSent && (
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
        )}

        {/* Magic link sent confirmation */}
        {magicLinkSent && !resetSent && (
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
              <Mail size={24} />
            </div>
            <p style={{ color: "#fff", fontWeight: 500, marginBottom: "8px" }}>Check your email</p>
            <p style={{ fontSize: "14px", color: "#6B7280", marginBottom: "20px" }}>
              We sent a sign-in link to {email}
            </p>
            <button
              onClick={() => { setMagicLinkMode(false); setMagicLinkSent(false); }}
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

        {/* Main login form */}
        {!resetSent && !magicLinkSent && (
          <>
            {/* Google SSO button */}
            {!resetMode && !magicLinkMode && (
              <div style={{ marginBottom: "20px" }}>
                <button
                  onClick={handleGoogleLogin}
                  disabled={googleLoading}
                  style={{
                    width: "100%",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: "12px",
                    padding: "14px 18px",
                    borderRadius: "12px",
                    border: "none",
                    background: "rgba(255,255,255,0.95)",
                    color: "#1f2937",
                    fontFamily: "inherit",
                    fontSize: "15px",
                    fontWeight: 500,
                    cursor: googleLoading ? "not-allowed" : "pointer",
                    opacity: googleLoading ? 0.6 : 1,
                    transition: "all 0.2s",
                  }}
                >
                  {googleLoading ? (
                    <div style={{ width: 20, height: 20, border: "2px solid #d1d5db", borderTopColor: "#4b5563", borderRadius: "50%", animation: "spin 1s linear infinite" }} />
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
                <div style={{ display: "flex", alignItems: "center", gap: "12px", margin: "20px 0" }}>
                  <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.06)" }} />
                  <span style={{ fontSize: "11px", color: "#6B7280", textTransform: "uppercase", letterSpacing: "1px" }}>or</span>
                  <div style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.06)" }} />
                </div>
              </div>
            )}

            <form onSubmit={resetMode ? handleReset : magicLinkMode ? handleMagicLink : handleLogin}>
              {/* Email field */}
              <div style={{ marginBottom: "22px" }}>
                <label style={{ display: "block", fontSize: "14px", fontWeight: 500, color: "#B0B8C8", marginBottom: "8px" }}>
                  Email Address
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@company.co.za"
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

              {/* Password field (only for standard login) */}
              {!resetMode && !magicLinkMode && (
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

              {/* Remember me / Forgot / Magic link */}
              {!resetMode && !magicLinkMode && (
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

              {/* Submit button */}
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
                {loading
                  ? "Please wait..."
                  : resetMode
                  ? "Send Reset Link"
                  : magicLinkMode
                  ? "Send Sign-in Link"
                  : "Sign In"}
              </button>

              {/* Magic link option (below password login) */}
              {!resetMode && !magicLinkMode && (
                <div style={{ textAlign: "center", marginTop: "14px" }}>
                  <button
                    type="button"
                    onClick={() => { setMagicLinkMode(true); setError(""); }}
                    style={{
                      background: "none",
                      border: "none",
                      color: "#6B7280",
                      cursor: "pointer",
                      fontSize: "13px",
                      fontFamily: "inherit",
                      display: "inline-flex",
                      alignItems: "center",
                      gap: "6px",
                    }}
                  >
                    <Mail size={14} />
                    Sign in with email link instead
                  </button>
                </div>
              )}

              {/* Back to login from sub-modes */}
              {(resetMode || magicLinkMode) && (
                <div style={{ textAlign: "center", marginTop: "16px" }}>
                  <button
                    type="button"
                    onClick={() => { setResetMode(false); setMagicLinkMode(false); setError(""); }}
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
              {!resetMode && !magicLinkMode && (
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
          </>
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
