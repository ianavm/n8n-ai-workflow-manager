"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Settings, Check, Eye, EyeOff, Shield, FileText } from "lucide-react";
import Link from "next/link";

const PASSWORD_RULES = [
  { test: (p: string) => p.length >= 8, label: "At least 8 characters" },
  { test: (p: string) => /[A-Z]/.test(p), label: "One uppercase letter" },
  { test: (p: string) => /[a-z]/.test(p), label: "One lowercase letter" },
  { test: (p: string) => /[0-9]/.test(p), label: "One number" },
  { test: (p: string) => /[!@#$%^&*(),.?":{}|<>]/.test(p), label: "One special character" },
];

interface ClientProfile {
  full_name: string;
  email: string;
  company_name: string | null;
  phone_number: string | null;
  email_verified: boolean;
  created_at: string;
}

export default function SettingsPage() {
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState("");

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState("");
  const [passwordError, setPasswordError] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  const supabase = createClient();

  useEffect(() => {
    async function loadProfile() {
      const res = await fetch("/api/portal/settings");
      if (res.ok) {
        const data = await res.json();
        setProfile(data);
        setFullName(data.full_name);
        setCompanyName(data.company_name || "");
        setPhoneNumber(data.phone_number || "");
      }
      setProfileLoading(false);
    }
    loadProfile();
  }, []);

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMessage("");

    const res = await fetch("/api/portal/settings", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        full_name: fullName,
        company_name: companyName || null,
        phone_number: phoneNumber || null,
      }),
    });

    if (res.ok) {
      setProfileMessage("Profile updated successfully");
      setProfile((prev) =>
        prev ? { ...prev, full_name: fullName, company_name: companyName || null, phone_number: phoneNumber || null } : prev
      );
    } else {
      const data = await res.json();
      setProfileMessage(data.error || "Failed to update profile");
    }
    setProfileSaving(false);
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPasswordError("");
    setPasswordMessage("");

    if (newPassword !== confirmPassword) {
      setPasswordError("Passwords do not match");
      return;
    }

    const allRulesPassed = PASSWORD_RULES.every((r) => r.test(newPassword));
    if (!allRulesPassed) {
      setPasswordError("Password does not meet all requirements");
      return;
    }

    setPasswordLoading(true);

    const { error } = await supabase.auth.updateUser({ password: newPassword });

    if (error) {
      setPasswordError("Failed to update password. Please try again.");
    } else {
      setPasswordMessage("Password updated successfully");
      setNewPassword("");
      setConfirmPassword("");
    }
    setPasswordLoading(false);
  }

  if (profileLoading) {
    return (
      <div className="max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-white">Settings</h1>
        <Card>
          <div className="animate-pulse space-y-4 p-2">
            <div className="h-4 bg-[rgba(255,255,255,0.05)] rounded w-1/3" />
            <div className="h-10 bg-[rgba(255,255,255,0.05)] rounded" />
            <div className="h-10 bg-[rgba(255,255,255,0.05)] rounded" />
            <div className="h-10 bg-[rgba(255,255,255,0.05)] rounded" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-3xl space-y-6">
      <div className="flex items-center gap-3">
        <Settings size={24} className="text-[#6366F1]" />
        <h1 className="text-2xl font-bold text-white">Settings</h1>
      </div>

      {/* Account Information */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-6">Account Information</h2>
        <form onSubmit={handleProfileSave} className="space-y-5">
          <Input
            label="Full Name"
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            required
          />

          <div>
            <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
              Email
            </label>
            <div className="flex items-center gap-3">
              <div className="flex-1 px-3 py-2.5 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] text-sm text-[#6B7280]">
                {profile?.email}
              </div>
              <Badge variant={profile?.email_verified ? "success" : "warning"}>
                {profile?.email_verified ? "Verified" : "Unverified"}
              </Badge>
            </div>
          </div>

          <Input
            label="Company Name"
            type="text"
            value={companyName}
            onChange={(e) => setCompanyName(e.target.value)}
            placeholder="Optional"
          />

          <Input
            label="Phone Number"
            type="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="Optional"
          />

          {profileMessage && (
            <p className={`text-sm px-3 py-2 rounded-lg ${
              profileMessage.includes("success")
                ? "text-[#00D4AA] bg-emerald-500/10 border border-emerald-500/20"
                : "text-red-400 bg-red-500/10 border border-red-500/20"
            }`}>
              {profileMessage}
            </p>
          )}

          <Button type="submit" variant="primary" loading={profileSaving}>
            Save Changes
          </Button>
        </form>
      </Card>

      {/* Change Password */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-6">Change Password</h2>
        <form onSubmit={handlePasswordChange} className="space-y-5">
          <div className="relative">
            <Input
              label="New Password"
              type={showPassword ? "text" : "password"}
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
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
          {newPassword && (
            <div className="space-y-1.5 px-1">
              {PASSWORD_RULES.map((rule) => {
                const passed = rule.test(newPassword);
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
              error={confirmPassword && newPassword !== confirmPassword ? "Passwords do not match" : undefined}
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

          {passwordError && (
            <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
              {passwordError}
            </p>
          )}

          {passwordMessage && (
            <p className="text-sm text-[#00D4AA] bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">
              {passwordMessage}
            </p>
          )}

          <Button type="submit" variant="primary" loading={passwordLoading}>
            Update Password
          </Button>
        </form>
      </Card>

      {/* Account Info */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-3">Account Details</h2>
        <div className="text-sm text-[#71717A] space-y-2">
          <p>Member since: {profile?.created_at ? new Date(profile.created_at).toLocaleDateString("en-ZA", { year: "numeric", month: "long", day: "numeric" }) : "N/A"}</p>
        </div>
      </Card>

      {/* Security & Legal */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-4">Security & Legal</h2>
        <div className="space-y-3">
          <Link
            href="/portal/settings/security"
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)] transition-colors text-sm text-[#A1A1AA] hover:text-white no-underline"
          >
            <Shield size={18} className="text-[#6366F1]" />
            Security Settings
            <span className="ml-auto text-[#52525B]">&rarr;</span>
          </Link>
          <Link
            href="/portal/legal/privacy"
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)] transition-colors text-sm text-[#A1A1AA] hover:text-white no-underline"
          >
            <FileText size={18} className="text-[#71717A]" />
            Privacy Policy
            <span className="ml-auto text-[#52525B]">&rarr;</span>
          </Link>
          <Link
            href="/portal/legal/terms"
            className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(255,255,255,0.12)] transition-colors text-sm text-[#A1A1AA] hover:text-white no-underline"
          >
            <FileText size={18} className="text-[#71717A]" />
            Terms of Service
            <span className="ml-auto text-[#52525B]">&rarr;</span>
          </Link>
        </div>
      </Card>
    </div>
  );
}
