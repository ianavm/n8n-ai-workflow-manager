"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Check,
  CheckCircle2,
  Eye,
  EyeOff,
  FileText,
  Shield,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";

import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";
import { Input } from "@/components/ui-shadcn/input";
import { Badge } from "@/components/ui-shadcn/badge";
import { Field } from "@/components/ui-shadcn/field";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui-shadcn/tabs";
import { cn } from "@/lib/utils";

const PASSWORD_RULES: Array<{ test: (p: string) => boolean; label: string }> = [
  { test: (p) => p.length >= 8,               label: "At least 8 characters" },
  { test: (p) => /[A-Z]/.test(p),             label: "One uppercase letter" },
  { test: (p) => /[a-z]/.test(p),             label: "One lowercase letter" },
  { test: (p) => /[0-9]/.test(p),             label: "One number" },
  { test: (p) => /[!@#$%^&*(),.?":{}|<>]/.test(p), label: "One special character" },
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
  const supabase = createClient();
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [phoneNumber, setPhoneNumber] = useState("");
  const [profileLoading, setProfileLoading] = useState(true);
  const [profileSaving, setProfileSaving] = useState(false);
  const [profileMessage, setProfileMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [passwordMessage, setPasswordMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);

  useEffect(() => {
    async function loadProfile() {
      try {
        const res = await fetch("/api/portal/settings");
        if (res.ok) {
          const data = await res.json();
          setProfile(data);
          setFullName(data.full_name);
          setCompanyName(data.company_name || "");
          setPhoneNumber(data.phone_number || "");
        }
      } finally {
        setProfileLoading(false);
      }
    }
    loadProfile();
  }, []);

  async function handleProfileSave(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    setProfileMessage(null);

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
      setProfileMessage({ type: "success", text: "Profile updated successfully." });
      setProfile((prev) =>
        prev
          ? {
              ...prev,
              full_name: fullName,
              company_name: companyName || null,
              phone_number: phoneNumber || null,
            }
          : prev,
      );
    } else {
      const data = await res.json().catch(() => ({}));
      setProfileMessage({ type: "error", text: data.error || "Failed to update profile." });
    }
    setProfileSaving(false);
  }

  async function handlePasswordChange(e: React.FormEvent) {
    e.preventDefault();
    setPasswordMessage(null);

    if (newPassword !== confirmPassword) {
      setPasswordMessage({ type: "error", text: "Passwords do not match." });
      return;
    }
    if (!PASSWORD_RULES.every((r) => r.test(newPassword))) {
      setPasswordMessage({ type: "error", text: "Password does not meet all requirements." });
      return;
    }

    setPasswordLoading(true);
    const { error } = await supabase.auth.updateUser({ password: newPassword });
    if (error) {
      setPasswordMessage({ type: "error", text: "Failed to update password. Please try again." });
    } else {
      setPasswordMessage({ type: "success", text: "Password updated successfully." });
      setNewPassword("");
      setConfirmPassword("");
    }
    setPasswordLoading(false);
  }

  if (profileLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-4xl">
        <PageHeader eyebrow="Settings" title="Account settings" description="Manage your profile, security, and preferences." />
        <LoadingState variant="card" rows={5} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 max-w-4xl">
      <PageHeader
        eyebrow="Settings"
        title="Account settings"
        description="Manage your profile, security, and preferences."
      />

      <Tabs defaultValue="profile">
        <TabsList variant="line" className="overflow-x-auto no-scrollbar">
          <TabsTrigger value="profile">Profile</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="account">Account</TabsTrigger>
          <TabsTrigger value="legal">Legal</TabsTrigger>
        </TabsList>

        {/* Profile tab */}
        <TabsContent value="profile" className="mt-6">
          <Card variant="default" padding="lg">
            <CardHeader>
              <CardTitle className="text-base">Profile information</CardTitle>
              <CardDescription>Update your personal and business details.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handleProfileSave} className="flex flex-col gap-5">
                <div className="grid gap-4 md:grid-cols-2">
                  <Field label="Full name" required>
                    <Input
                      type="text"
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      required
                    />
                  </Field>

                  <Field label="Email">
                    <div className="flex items-center gap-2 h-10 px-4 rounded-[10px] border border-[var(--border-subtle)] bg-[var(--input)] text-sm text-[var(--text-muted)]">
                      <span className="truncate flex-1">{profile?.email ?? "—"}</span>
                      <Badge
                        tone={profile?.email_verified ? "success" : "warning"}
                        appearance="soft"
                        size="sm"
                      >
                        {profile?.email_verified ? "Verified" : "Unverified"}
                      </Badge>
                    </div>
                  </Field>
                </div>

                <Field label="Company name" hint="Optional. Shown on invoices and reports.">
                  <Input
                    type="text"
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    placeholder="e.g. AnyVision Media"
                  />
                </Field>

                <Field label="Phone number" hint="Optional. Used for critical account alerts.">
                  <Input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="+27 ..."
                  />
                </Field>

                {profileMessage ? (
                  <FormMessage type={profileMessage.type} text={profileMessage.text} />
                ) : null}

                <div className="flex justify-end">
                  <Button type="submit" variant="default" loading={profileSaving}>
                    Save changes
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Security tab */}
        <TabsContent value="security" className="mt-6 flex flex-col gap-6">
          <Card variant="default" padding="lg">
            <CardHeader>
              <CardTitle className="text-base">Change password</CardTitle>
              <CardDescription>
                Use a strong password you don&rsquo;t use anywhere else.
              </CardDescription>
            </CardHeader>
            <CardContent className="pt-6">
              <form onSubmit={handlePasswordChange} className="flex flex-col gap-5">
                <Field label="New password" required>
                  <div className="relative">
                    <Input
                      type={showPassword ? "text" : "password"}
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Enter new password"
                      required
                      autoComplete="new-password"
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((v) => !v)}
                      tabIndex={-1}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] hover:text-foreground transition-colors"
                    >
                      {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </Field>

                {newPassword ? (
                  <ul className="flex flex-col gap-1.5 px-1">
                    {PASSWORD_RULES.map((rule) => {
                      const passed = rule.test(newPassword);
                      return (
                        <li key={rule.label} className="flex items-center gap-2 text-xs">
                          <span
                            className={cn(
                              "size-3.5 shrink-0 rounded-full grid place-items-center",
                              passed
                                ? "bg-[color-mix(in_srgb,var(--accent-teal)_20%,transparent)] text-[var(--accent-teal)]"
                                : "bg-[color-mix(in_srgb,var(--text-white)_5%,transparent)] text-[var(--text-dim)]",
                            )}
                            aria-hidden
                          >
                            {passed ? <Check className="size-2.5" /> : null}
                          </span>
                          <span className={passed ? "text-foreground" : "text-[var(--text-dim)]"}>
                            {rule.label}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                ) : null}

                <Field
                  label="Confirm new password"
                  required
                  error={
                    confirmPassword && newPassword !== confirmPassword
                      ? "Passwords do not match"
                      : undefined
                  }
                >
                  <div className="relative">
                    <Input
                      type={showConfirm ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Confirm new password"
                      required
                      autoComplete="new-password"
                      className="pr-10"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirm((v) => !v)}
                      tabIndex={-1}
                      aria-label={showConfirm ? "Hide password" : "Show password"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)] hover:text-foreground transition-colors"
                    >
                      {showConfirm ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                    </button>
                  </div>
                </Field>

                {passwordMessage ? (
                  <FormMessage type={passwordMessage.type} text={passwordMessage.text} />
                ) : null}

                <div className="flex justify-end">
                  <Button type="submit" variant="default" loading={passwordLoading}>
                    Update password
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>

          <Card variant="default" padding="lg">
            <SettingsLinkRow
              href="/portal/settings/security"
              icon={<Shield className="size-4" />}
              iconColor="var(--accent-purple)"
              title="Security settings"
              description="Two-factor authentication, active sessions, and audit log."
            />
          </Card>
        </TabsContent>

        {/* Account tab */}
        <TabsContent value="account" className="mt-6">
          <Card variant="default" padding="lg">
            <CardHeader>
              <CardTitle className="text-base">Account details</CardTitle>
              <CardDescription>Read-only details about your account.</CardDescription>
            </CardHeader>
            <CardContent className="pt-6 flex flex-col gap-3 text-sm">
              <Row label="Member since">
                {profile?.created_at
                  ? new Date(profile.created_at).toLocaleDateString("en-ZA", {
                      day: "numeric",
                      month: "long",
                      year: "numeric",
                    })
                  : "—"}
              </Row>
              <Row label="Email status">
                <Badge
                  tone={profile?.email_verified ? "success" : "warning"}
                  appearance="soft"
                  size="sm"
                >
                  {profile?.email_verified ? "Verified" : "Unverified"}
                </Badge>
              </Row>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Legal tab */}
        <TabsContent value="legal" className="mt-6">
          <Card variant="default" padding="none">
            <ul className="divide-y divide-[var(--border-subtle)]">
              <li>
                <SettingsLinkRow
                  href="/portal/legal/privacy"
                  icon={<FileText className="size-4" />}
                  title="Privacy policy"
                  description="How we collect and protect your data."
                />
              </li>
              <li>
                <SettingsLinkRow
                  href="/portal/legal/terms"
                  icon={<FileText className="size-4" />}
                  title="Terms of service"
                  description="Rules for using the AnyVision platform."
                />
              </li>
            </ul>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function FormMessage({ type, text }: { type: "success" | "error"; text: string }) {
  return (
    <p
      role={type === "error" ? "alert" : undefined}
      className={cn(
        "flex items-center gap-2 text-sm px-3 py-2 rounded-[var(--radius-sm)]",
        type === "success"
          ? "text-[var(--accent-teal)] bg-[color-mix(in_srgb,var(--accent-teal)_10%,transparent)] border border-[color-mix(in_srgb,var(--accent-teal)_30%,transparent)]"
          : "text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_30%,transparent)]",
      )}
    >
      {type === "success" ? (
        <CheckCircle2 className="size-4 shrink-0" aria-hidden />
      ) : null}
      {text}
    </p>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 py-2 border-b border-[var(--border-subtle)] last:border-0">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="font-medium text-foreground">{children}</span>
    </div>
  );
}

function SettingsLinkRow({
  href,
  icon,
  title,
  description,
  iconColor = "var(--text-muted)",
}: {
  href: string;
  icon: React.ReactNode;
  title: string;
  description: string;
  iconColor?: string;
}) {
  return (
    <Link
      href={href}
      className="group flex items-center gap-4 px-5 py-4 hover:bg-[var(--bg-card-hover)] transition-colors rounded-[var(--radius-sm)]"
    >
      <span
        className="grid place-items-center size-10 rounded-[var(--radius-sm)] shrink-0"
        style={{
          background: `color-mix(in srgb, ${iconColor} 12%, transparent)`,
          color: iconColor,
        }}
      >
        {icon}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-xs text-[var(--text-muted)] mt-0.5">{description}</p>
      </div>
      <ArrowRight className="size-4 text-[var(--text-dim)] group-hover:text-foreground group-hover:translate-x-0.5 transition-all" aria-hidden />
    </Link>
  );
}
