"use client";

import { useState, useEffect } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import {
  Shield,
  ShieldCheck,
  Monitor,
  LogOut,
  Clock,
  MapPin,
  Smartphone,
  Key,
} from "lucide-react";
import Link from "next/link";

interface SecurityInfo {
  last_login_at: string | null;
  last_login_ip: string | null;
  last_login_device: string | null;
  created_at: string;
}

export default function SecuritySettingsPage() {
  const [info, setInfo] = useState<SecurityInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [signingOut, setSigningOut] = useState(false);
  const [signOutMessage, setSignOutMessage] = useState("");
  const supabase = createClient();

  useEffect(() => {
    async function loadSecurity() {
      const res = await fetch("/api/portal/settings/security");
      if (res.ok) {
        setInfo(await res.json());
      }
      setLoading(false);
    }
    loadSecurity();
  }, []);

  async function handleSignOutAll() {
    setSigningOut(true);
    setSignOutMessage("");
    const { error } = await supabase.auth.signOut({ scope: "global" });
    if (error) {
      setSignOutMessage("Failed to sign out all devices. Please try again.");
      setSigningOut(false);
    } else {
      window.location.href = "/portal/login";
    }
  }

  if (loading) {
    return (
      <div className="max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold text-white">Security</h1>
        <Card>
          <div className="animate-pulse space-y-4 p-2">
            <div className="h-4 bg-[rgba(255,255,255,0.05)] rounded w-1/3" />
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
        <Shield size={24} className="text-[#6366F1]" />
        <h1 className="text-2xl font-bold text-white">Security</h1>
      </div>

      <p className="text-sm text-[#71717A]">
        Manage your account security, review recent activity, and control your sessions.
      </p>

      {/* Last Login Activity */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-5">Recent Login Activity</h2>
        <div className="space-y-4">
          {info?.last_login_at ? (
            <>
              <div className="flex items-center gap-3 text-sm">
                <Clock size={16} className="text-[#71717A] flex-shrink-0" />
                <span className="text-[#A1A1AA]">Last login:</span>
                <span className="text-white">
                  {new Date(info.last_login_at).toLocaleDateString("en-ZA", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              {info.last_login_device && (
                <div className="flex items-center gap-3 text-sm">
                  <Monitor size={16} className="text-[#71717A] flex-shrink-0" />
                  <span className="text-[#A1A1AA]">Device:</span>
                  <span className="text-white">{info.last_login_device}</span>
                </div>
              )}
              {info.last_login_ip && (
                <div className="flex items-center gap-3 text-sm">
                  <MapPin size={16} className="text-[#71717A] flex-shrink-0" />
                  <span className="text-[#A1A1AA]">IP Address:</span>
                  <span className="text-white font-mono text-xs">{info.last_login_ip}</span>
                </div>
              )}
            </>
          ) : (
            <p className="text-sm text-[#71717A]">No login activity recorded yet.</p>
          )}
        </div>
      </Card>

      {/* Two-Factor Authentication */}
      <Card>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-white">Two-Factor Authentication</h2>
          <Badge variant="warning">Coming Soon</Badge>
        </div>
        <div className="flex items-start gap-3">
          <Key size={18} className="text-[#71717A] mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-[#A1A1AA]">
              Add an extra layer of security to your account by enabling two-factor authentication
              with an authenticator app (Google Authenticator, Authy, etc.).
            </p>
            <p className="text-xs text-[#52525B] mt-2">
              This feature is being rolled out and will be available shortly.
            </p>
          </div>
        </div>
      </Card>

      {/* Active Sessions */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-4">Session Management</h2>
        <div className="flex items-start gap-3 mb-5">
          <Smartphone size={18} className="text-[#71717A] mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm text-[#A1A1AA]">
              If you suspect unauthorized access, sign out of all devices immediately.
              You will need to log in again on this device.
            </p>
          </div>
        </div>

        {signOutMessage && (
          <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 mb-4">
            {signOutMessage}
          </p>
        )}

        <Button
          variant="danger"
          onClick={handleSignOutAll}
          loading={signingOut}
        >
          <LogOut size={16} />
          Sign Out All Devices
        </Button>
      </Card>

      {/* Security Status */}
      <Card>
        <h2 className="text-lg font-semibold text-white mb-4">Security Status</h2>
        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-[#A1A1AA]">
              <ShieldCheck size={16} className="text-emerald-400" />
              Password authentication
            </div>
            <Badge variant="success">Active</Badge>
          </div>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-[#A1A1AA]">
              <Shield size={16} className="text-[#71717A]" />
              Two-factor authentication
            </div>
            <Badge variant="default">Not enabled</Badge>
          </div>
          <div className="flex items-center justify-between text-sm">
            <div className="flex items-center gap-2 text-[#A1A1AA]">
              <Clock size={16} className="text-emerald-400" />
              Auto-logout (30 min inactivity)
            </div>
            <Badge variant="success">Active</Badge>
          </div>
        </div>
      </Card>

      {/* Back link */}
      <div className="pt-2">
        <Link href="/portal/settings" className="text-sm text-[#71717A] hover:text-[#A1A1AA] no-underline">
          &larr; Back to Settings
        </Link>
      </div>
    </div>
  );
}
