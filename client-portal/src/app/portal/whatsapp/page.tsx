"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { MessageCircle } from "lucide-react";

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

// Meta App ID — set after Meta verification is approved
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
    if (!user) return;

    const { data: profile } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .single();

    if (!profile) return;
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
      }
    );
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Load Meta Facebook SDK
  useEffect(() => {
    if (!META_APP_ID) return;

    // Prevent double-loading
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
      setError(
        "WhatsApp integration is not yet available. Meta Business Verification is pending."
      );
      return;
    }

    if (!window.FB) {
      setError("Facebook SDK failed to load. Please refresh and try again.");
      return;
    }

    setConnecting(true);
    setError(null);

    try {
      // Launch Meta Embedded Signup flow
      window.FB.login(
        function (response: { authResponse?: { code?: string } }) {
          if (response.authResponse?.code) {
            // Exchange the auth code for credentials via our API
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
            setup: {
              // Enable coexistence: client keeps their WA Business app
              solutionID: process.env.NEXT_PUBLIC_META_SOLUTION_ID || "",
            },
          },
        }
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

      if (!res.ok) {
        throw new Error(data.error || "Failed to connect WhatsApp");
      }

      // Refresh config to show connected state
      await fetchConfig();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to connect WhatsApp"
      );
    } finally {
      setConnecting(false);
    }
  }

  async function handleDisconnect() {
    if (!clientId) return;

    const confirmed = window.confirm(
      "Are you sure you want to disconnect WhatsApp? Your WhatsApp Business app will continue working normally."
    );
    if (!confirmed) return;

    const res = await fetch("/api/portal/whatsapp", {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ client_id: clientId }),
    });

    if (res.ok) {
      await fetchConfig();
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full" />
      </div>
    );
  }

  const isConnected = config?.status === "connected";
  const isPending = config?.status === "pending";

  return (
    <div className="space-y-8 max-w-3xl">
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            WhatsApp <span className="gradient-text">Setup</span>
          </h1>
          <p className="text-base text-[#B0B8C8] mt-2">
            Connect your WhatsApp Business number for AI auto-replies
          </p>
        </div>
      </div>

      {/* Status Card */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {/* WhatsApp icon */}
            <div
              className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                isConnected
                  ? "bg-emerald-500/10"
                  : "bg-[rgba(255,255,255,0.05)]"
              }`}
            >
              <svg
                width="22"
                height="22"
                viewBox="0 0 24 24"
                fill={isConnected ? "#10B981" : "#6B7280"}
              >
                <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
              </svg>
            </div>
            <div>
              <h3 className="text-white font-medium">
                {isConnected
                  ? "WhatsApp Connected"
                  : isPending
                    ? "Connection Pending"
                    : "WhatsApp Not Connected"}
              </h3>
              <p className="text-xs text-[#6B7280] mt-0.5">
                {isConnected
                  ? `${config?.display_phone_number} via Cloud API`
                  : isPending
                    ? "Waiting for Meta verification"
                    : "Connect your WhatsApp Business number to enable AI auto-replies"}
              </p>
            </div>
          </div>
          <Badge
            variant={
              isConnected ? "success" : isPending ? "warning" : "danger"
            }
          >
            {config?.status || "not_connected"}
          </Badge>
        </div>
      </Card>

      {/* Connection Details (when connected) */}
      {isConnected && config && (
        <Card>
          <h2 className="text-sm font-semibold text-white mb-4">
            Connection Details
          </h2>
          <div className="space-y-3">
            <div className="flex justify-between text-sm">
              <span className="text-[#6B7280]">Phone Number</span>
              <span className="text-white">
                {config.display_phone_number || "-"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-[#6B7280]">Business Name</span>
              <span className="text-white">
                {config.business_name || "-"}
              </span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-[#6B7280]">Coexistence Mode</span>
              <Badge variant={config.coexistence_enabled ? "success" : "warning"}>
                {config.coexistence_enabled ? "Enabled" : "Disabled"}
              </Badge>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-[#6B7280]">Connected Since</span>
              <span className="text-white">
                {config.connected_at
                  ? new Date(config.connected_at).toLocaleDateString()
                  : "-"}
              </span>
            </div>
          </div>

          <div className="mt-6 pt-4 border-t border-[rgba(255,255,255,0.06)]">
            <button
              onClick={handleDisconnect}
              className="text-xs text-red-400 hover:text-red-300 transition-colors"
            >
              Disconnect WhatsApp
            </button>
          </div>
        </Card>
      )}

      {/* Coexistence Info */}
      {!isConnected && (
        <Card>
          <h2 className="text-sm font-semibold text-white mb-3">
            How It Works
          </h2>
          <div className="space-y-3 text-sm text-[#B0B8C8]">
            <div className="flex gap-3">
              <span className="text-[#6C63FF] font-bold flex-shrink-0">1.</span>
              <p>
                Click &quot;Connect WhatsApp&quot; below to link your existing
                WhatsApp Business number.
              </p>
            </div>
            <div className="flex gap-3">
              <span className="text-[#6C63FF] font-bold flex-shrink-0">2.</span>
              <p>
                Your WhatsApp Business app stays active on your phone
                — nothing changes for you.
              </p>
            </div>
            <div className="flex gap-3">
              <span className="text-[#6C63FF] font-bold flex-shrink-0">3.</span>
              <p>
                Our AI assistant will handle incoming messages automatically via
                the Cloud API, running alongside your app.
              </p>
            </div>
            <div className="flex gap-3">
              <span className="text-[#6C63FF] font-bold flex-shrink-0">4.</span>
              <p>
                Messages sync between your phone and the AI — you can see
                everything in both places.
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Error Message */}
      {error && (
        <div className="rounded-lg bg-red-500/10 border border-red-500/20 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Connect / Reconnect Button */}
      {!isConnected && (
        <Button onClick={handleConnect} disabled={connecting}>
          {connecting ? (
            <span className="flex items-center gap-2">
              <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
              Connecting...
            </span>
          ) : (
            "Connect WhatsApp"
          )}
        </Button>
      )}
    </div>
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
        options: Record<string, unknown>
      ) => void;
    };
  }
}
