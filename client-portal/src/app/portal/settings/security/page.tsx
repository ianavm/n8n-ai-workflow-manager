"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Clock,
  Key,
  LogOut,
  MapPin,
  Monitor,
  Shield,
  ShieldCheck,
  Smartphone,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui-shadcn/card";

interface SecurityInfo {
  last_login_at: string | null;
  last_login_ip: string | null;
  last_login_device: string | null;
  created_at: string;
}

export default function SecuritySettingsPage() {
  const supabase = createClient();
  const [info, setInfo] = useState<SecurityInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutError, setSignOutError] = useState("");

  useEffect(() => {
    async function loadSecurity() {
      const res = await fetch("/api/portal/settings/security");
      if (res.ok) setInfo(await res.json());
      setLoading(false);
    }
    loadSecurity();
  }, []);

  async function handleSignOutAll() {
    setSigningOut(true);
    setSignOutError("");
    const { error } = await supabase.auth.signOut({ scope: "global" });
    if (error) {
      setSignOutError("Failed to sign out all devices. Please try again.");
      setSigningOut(false);
    } else {
      window.location.href = "/portal/login";
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <PageHeader
          eyebrow="Settings"
          title="Security"
          description="Manage your account security, review recent activity, and control your sessions."
        />
        <LoadingState variant="card" rows={5} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-8 max-w-3xl">
      <PageHeader
        eyebrow="Settings"
        title="Security"
        description="Manage your account security, review recent activity, and control your sessions."
      />

      {/* Recent login activity */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Recent login activity</CardTitle>
        </CardHeader>
        <CardContent className="pt-4 flex flex-col gap-3">
          {info?.last_login_at ? (
            <>
              <Row
                icon={<Clock className="size-4" />}
                label="Last login"
                value={new Date(info.last_login_at).toLocaleDateString("en-ZA", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              />
              {info.last_login_device ? (
                <Row
                  icon={<Monitor className="size-4" />}
                  label="Device"
                  value={info.last_login_device}
                />
              ) : null}
              {info.last_login_ip ? (
                <Row
                  icon={<MapPin className="size-4" />}
                  label="IP address"
                  value={<span className="font-mono text-xs">{info.last_login_ip}</span>}
                />
              ) : null}
            </>
          ) : (
            <p className="text-sm text-[var(--text-muted)]">No login activity recorded yet.</p>
          )}
        </CardContent>
      </Card>

      {/* 2FA */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <CardTitle className="text-base">Two-factor authentication</CardTitle>
            <Badge tone="warning" appearance="soft" size="sm">
              Coming soon
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="flex items-start gap-3">
            <span className="grid place-items-center size-10 rounded-[var(--radius-sm)] bg-[var(--bg-card-hover)] text-[var(--text-muted)] shrink-0">
              <Key className="size-4" aria-hidden />
            </span>
            <div className="flex-1">
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                Add an extra layer of security to your account by enabling two-factor authentication
                with an authenticator app (Google Authenticator, Authy, etc.).
              </p>
              <p className="text-xs text-[var(--text-dim)] mt-2">
                This feature is being rolled out and will be available shortly.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Active sessions */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Session management</CardTitle>
          <CardDescription>
            If you suspect unauthorized access, sign out everywhere and log back in.
          </CardDescription>
        </CardHeader>
        <CardContent className="pt-4 flex flex-col gap-4">
          <div className="flex items-start gap-3">
            <span className="grid place-items-center size-10 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)] shrink-0">
              <Smartphone className="size-4" aria-hidden />
            </span>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed">
              Signing out all devices ends every active session (browsers, mobile, tablets) and
              requires you to log in again on this device.
            </p>
          </div>

          {signOutError ? (
            <p
              role="alert"
              className="text-sm text-[var(--danger)] bg-[color-mix(in_srgb,var(--danger)_10%,transparent)] border border-[color-mix(in_srgb,var(--danger)_25%,transparent)] rounded-[var(--radius-sm)] px-3 py-2"
            >
              {signOutError}
            </p>
          ) : null}

          <div>
            <Button variant="destructive" onClick={handleSignOutAll} loading={signingOut}>
              <LogOut className="size-4" />
              Sign out all devices
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Security status */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Security status</CardTitle>
        </CardHeader>
        <CardContent className="pt-4 flex flex-col gap-3">
          <StatusRow
            icon={<ShieldCheck className="size-4 text-[var(--accent-teal)]" />}
            label="Password authentication"
            badge={<Badge tone="success" appearance="soft" size="sm">Active</Badge>}
          />
          <StatusRow
            icon={<Shield className="size-4 text-[var(--text-dim)]" />}
            label="Two-factor authentication"
            badge={<Badge tone="neutral" appearance="soft" size="sm">Not enabled</Badge>}
          />
          <StatusRow
            icon={<Clock className="size-4 text-[var(--accent-teal)]" />}
            label="Auto-logout (30 min inactivity)"
            badge={<Badge tone="success" appearance="soft" size="sm">Active</Badge>}
          />
        </CardContent>
      </Card>

      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link href="/portal/settings" className="gap-1.5">
          <ArrowLeft className="size-3.5" />
          Back to settings
        </Link>
      </Button>
    </div>
  );
}

function Row({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: React.ReactNode;
}) {
  return (
    <div className="flex items-center gap-3 text-sm">
      <span className="text-[var(--text-dim)] shrink-0">{icon}</span>
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="ml-auto font-medium text-foreground">{value}</span>
    </div>
  );
}

function StatusRow({
  icon,
  label,
  badge,
}: {
  icon: React.ReactNode;
  label: string;
  badge: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="flex items-center gap-2 text-[var(--text-muted)]">
        {icon}
        {label}
      </span>
      {badge}
    </div>
  );
}
