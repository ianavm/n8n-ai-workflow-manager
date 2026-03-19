"use client";

import { useState } from "react";
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

    // Check if user is an admin
    if (data.user) {
      const { data: adminUser } = await supabase
        .from("admin_users")
        .select("id")
        .eq("auth_user_id", data.user.id)
        .single();

      if (adminUser) {
        router.push("/admin");
        router.refresh();
        return;
      }
    }

    router.push("/portal");
    router.refresh();
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

            {/* Divider + social login */}
            {!resetMode && (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "16px",
                    margin: "28px 0",
                    fontSize: "13px",
                    color: "#6B7280",
                  }}
                >
                  <span style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.08)" }} />
                  or continue with
                  <span style={{ flex: 1, height: "1px", background: "rgba(255,255,255,0.08)" }} />
                </div>
                <div style={{ display: "flex", gap: "16px" }}>
                  <button
                    type="button"
                    style={{
                      flex: 1,
                      padding: "12px",
                      borderRadius: "12px",
                      border: "1px solid rgba(255,255,255,0.08)",
                      background: "rgba(255,255,255,0.03)",
                      color: "#B0B8C8",
                      fontFamily: "inherit",
                      fontSize: "13px",
                      fontWeight: 500,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0016 8c0-4.42-3.58-8-8-8z"/></svg>
                    GitHub
                  </button>
                  <button
                    type="button"
                    style={{
                      flex: 1,
                      padding: "12px",
                      borderRadius: "12px",
                      border: "1px solid rgba(255,255,255,0.08)",
                      background: "rgba(255,255,255,0.03)",
                      color: "#B0B8C8",
                      fontFamily: "inherit",
                      fontSize: "13px",
                      fontWeight: 500,
                      cursor: "pointer",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: "8px",
                      transition: "all 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
                    }}
                  >
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor"><path d="M15.68 8.18c0-.57-.05-1.12-.15-1.64H8v3.1h4.3a3.68 3.68 0 01-1.6 2.41v2h2.58c1.51-1.39 2.38-3.44 2.38-5.87z" fill="#4285F4"/><path d="M8 16c2.16 0 3.97-.72 5.29-1.94l-2.58-2a4.82 4.82 0 01-7.19-2.53H.9v2.06A8 8 0 008 16z" fill="#34A853"/><path d="M3.52 9.52a4.8 4.8 0 010-3.04V4.42H.9a8 8 0 000 7.16l2.62-2.06z" fill="#FBBC05"/><path d="M8 3.18a4.33 4.33 0 013.07 1.2l2.3-2.3A7.72 7.72 0 008 0 8 8 0 00.9 4.42l2.62 2.06A4.77 4.77 0 018 3.18z" fill="#EA4335"/></svg>
                    Google
                  </button>
                </div>
              </>
            )}

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
                <a
                  href="/portal/signup"
                  style={{ fontSize: "13px", color: "#6B7280", textDecoration: "none" }}
                >
                  Don&apos;t have an account? <span style={{ color: "#6C63FF" }}>Sign up</span>
                </a>
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
