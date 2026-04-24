"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, MessageCircle } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";
import { Button } from "@/components/ui-shadcn/button";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import { cn } from "@/lib/utils";

interface WhatsAppConfig {
  id: string;
  client_id: string;
  waba_id: string | null;
  phone_number_id: string | null;
  display_phone_number: string | null;
  business_name: string | null;
  status: "not_connected" | "pending" | "connected" | "error";
  connected_at: string | null;
  coexistence_enabled: boolean;
}

const META_APP_ID = process.env.NEXT_PUBLIC_META_APP_ID || "";

export default function WhatsAppSetupPage() {
  const supabase = createClient();
  const [config, setConfig] = useState<WhatsAppConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientId, setClientId] = useState<string | null>(null);

  const fetchConfig = useCallback(async () => {
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) {
      setLoading(false);
      return;
    }

    const { data: profile } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .single();
    if (!profile) {
      setLoading(false);
      return;
    }
    setClientId(profile.id);

    const { data } = await supabase
      .from("whatsapp_connections")
      .select("*")
      .eq("client_id", profile.id)
      .single();

    setConfig(
      data || {
        id: "",
        client_id: profile.id,
        waba_id: null,
        phone_number_id: null,
        display_phone_number: null,
        business_name: null,
        status: "not_connected",
        connected_at: null,
        coexistence_enabled: false,
      },
    );
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (!META_APP_ID) return;
    if (document.getElementById("facebook-jssdk")) return;

    window.fbAsyncInit = function () {
      window.FB.init({
        appId: META_APP_ID,
        autoLogAppEvents: true,
        xfbml: true,
        version: "v18.0",
      });
    };

    const script = document.createElement("script");
    script.id = "facebook-jssdk";
    script.src = "https://connect.facebook.net/en_US/sdk.js";
    script.async = true;
    script.defer = true;
    document.body.appendChild(script);
  }, []);

  async function handleConnect() {
    if (!META_APP_ID) {
      setError("WhatsApp integration is not yet available. Meta Business Verification is pending.");
      return;
    }
    if (!window.FB) {
      setError("Facebook SDK failed to load. Please refresh and try again.");
      return;
    }

    setConnecting(true);
    setError(null);

    try {
      window.FB.login(
        function (response: { authResponse?: { code?: string } }) {
          if (response.authResponse?.code) {
            exchangeCode(response.authResponse.code);
          } else {
            setConnecting(false);
            setError("WhatsApp connection was cancelled.");
          }
        },
        {
          config_id: process.env.NEXT_PUBLIC_META_CONFIG_ID || "",
          response_type: "code",
          override_default_response_type: true,
          extras: {
            setup: { solutionID: process.env.NEXT_PUBLIC_META_SOLUTION_ID || "" },
          },
        },
      );
    } catch {
      setConnecting(false);
      setError("Failed to start WhatsApp connection. Please try again.");
    }
  }

  async function exchangeCode(code: string) {
    try {
      const res = await fetch("/api/portal/whatsapp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, client_id: clientId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Failed to connect WhatsApp");
      await fetchConfig();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to connect WhatsApp");
    } finally {
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    if (!clientId) return;
    const confirmed = window.confirm(
      "Are you sure you want to disconnect WhatsApp? Your WhatsApp Business app will continue working normally.",
    );
    if (!confirmed) return;

    const res = await fetch("/api/portal/whatsapp", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId }),
    });
    if (res.ok) await fetchConfig();
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6 max-w-3xl">
        <PageHeader
          eyebrow="Operations"
          title="WhatsApp setup"
          description="Connect your WhatsApp Business number for AI auto-replies."
        />
        <LoadingState variant="card" rows={4} />
      </div>
    );
  }

  const isConnected = config?.status === "connected";
  const isPending = config?.status === "pending";
  const statusTone = isConnected ? "success" : isPending ? "warning" : "danger";

  return (
    <div className="flex flex-col gap-8 max-w-3xl">
      <PageHeader
        eyebrow="Operations"
        title="WhatsApp setup"
        description="Connect your WhatsApp Business number for AI auto-replies."
      />

      {/* Status card */}
      <Card variant="default" accent={isConnected ? "teal" : isPending ? "coral" : "none"} padding="md">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <span
              className={cn(
                "grid place-items-center size-10 rounded-[var(--radius-sm)] shrink-0",
                isConnected
                  ? "bg-[color-mix(in_srgb,var(--accent-teal)_12%,transparent)] text-[var(--accent-teal)]"
                  : "bg-[var(--bg-card-hover)] text-[var(--text-muted)]",
              )}
            >
              <MessageCircle className="size-4" aria-hidden />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">
                {isConnected
                  ? "WhatsApp connected"
                  : isPending
                    ? "Connection pending"
                    : "WhatsApp not connected"}
              </p>
              <p className="text-xs text-[var(--text-muted)] mt-0.5 truncate">
                {isConnected
                  ? `${config?.display_phone_number} via Cloud API`
                  : isPending
                    ? "Waiting for Meta verification"
                    : "Connect your WhatsApp Business number to enable AI auto-replies."}
              </p>
            </div>
          </div>
          <Badge tone={statusTone} appearance="soft" size="sm" className="capitalize shrink-0">
            {(config?.status || "not_connected").replace("_", " ")}
          </Badge>
        </div>
      </Card>

      {/* Connection details */}
      {isConnected && config ? (
        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Connection details</CardTitle>
          </CardHeader>
          <CardContent className="pt-4 flex flex-col gap-3">
            <DetailRow label="Phone number" value={config.display_phone_number || "—"} />
            <DetailRow label="Business name" value={config.business_name || "—"} />
            <DetailRow
              label="Coexistence mode"
              value={
                <Badge
                  tone={config.coexistence_enabled ? "success" : "warning"}
                  appearance="soft"
                  size="sm"
                >
                  {config.coexistence_enabled ? "Enabled" : "Disabled"}
                </Badge>
              }
            />
            <DetailRow
              label="Connected since"
              value={config.connected_at ? new Date(config.connected_at).toLocaleDateString("en-ZA") : "—"}
            />
            <div className="mt-3 pt-4 border-t border-[var(--border-subtle)]">
              <Button variant="ghost" size="sm" onClick={handleDisconnect} className="text-[var(--danger)] hover:text-[var(--danger)]">
                Disconnect WhatsApp
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : null}

      {/* How it works */}
      {!isConnected ? (
        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">How it works</CardTitle>
            <CardDescription>
              Connecting takes under a minute. Your existing WhatsApp Business app keeps working.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-4">
            <ol className="flex flex-col gap-3 text-sm text-[var(--text-muted)]">
              <Step n={1}>Click &ldquo;Connect WhatsApp&rdquo; below to link your existing WhatsApp Business number.</Step>
              <Step n={2}>Your WhatsApp Business app stays active on your phone — nothing changes for you.</Step>
              <Step n={3}>Our AI assistant handles incoming messages automatically via the Cloud API, running alongside your app.</Step>
              <Step n={4}>Messages sync between your phone and the AI — you can see everything in both places.</Step>
            </ol>
          </CardContent>
        </Card>
      ) : null}

      {/* Error */}
      {error ? (
        <Card
          variant="default"
          padding="md"
          className="border-[color-mix(in_srgb,var(--danger)_30%,transparent)] bg-[color-mix(in_srgb,var(--danger)_8%,transparent)]"
        >
          <div className="flex items-start gap-3">
            <AlertCircle className="size-4 text-[var(--danger)] shrink-0 mt-0.5" aria-hidden />
            <p className="text-sm text-[var(--danger)]">{error}</p>
          </div>
        </Card>
      ) : null}

      {/* Connect CTA */}
      {!isConnected ? (
        <div>
          <Button variant="default" onClick={handleConnect} loading={connecting}>
            {connecting ? "Connecting…" : "Connect WhatsApp"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between text-sm gap-3">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="font-medium text-foreground">{value}</span>
    </div>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-3">
      <span className="grid place-items-center size-6 rounded-full bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)] text-xs font-bold shrink-0">
        {n}
      </span>
      <span className="leading-relaxed">{children}</span>
    </li>
  );
}

// Type declarations for Meta Facebook SDK
declare global {
  interface Window {
    fbAsyncInit: () => void;
    FB: {
      init: (params: {
        appId: string;
        autoLogAppEvents: boolean;
        xfbml: boolean;
        version: string;
      }) => void;
      login: (
        callback: (response: { authResponse?: { code?: string } }) => void,
        options: Record<string, unknown>,
      ) => void;
    };
  }
}
