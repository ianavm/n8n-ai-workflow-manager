"use client";

import { useEffect, useState } from "react";
import { ConnectionCard } from "@/components/connections/ConnectionCard";
import { Plug, Shield, HelpCircle } from "lucide-react";

const PROVIDERS = [
  { id: "google_ads", name: "Google Ads", icon: "G", color: "#4285F4", description: "Search & display advertising campaigns", docsUrl: "https://ads.google.com" },
  { id: "meta_ads", name: "Meta Ads", icon: "M", color: "#0668E1", description: "Facebook & Instagram advertising", docsUrl: "https://business.facebook.com" },
  { id: "quickbooks", name: "QuickBooks", icon: "Q", color: "#2CA01C", description: "Accounting, invoicing & reconciliation", docsUrl: "https://quickbooks.intuit.com" },
  { id: "google_workspace", name: "Google Workspace", icon: "W", color: "#EA4335", description: "Gmail, Sheets, Drive & Calendar", docsUrl: "https://workspace.google.com" },
  { id: "tiktok_ads", name: "TikTok Ads", icon: "T", color: "#000000", description: "Short-form video advertising", docsUrl: "https://ads.tiktok.com" },
  { id: "linkedin_ads", name: "LinkedIn Ads", icon: "L", color: "#0A66C2", description: "B2B professional advertising", docsUrl: "https://www.linkedin.com/campaignmanager" },
  { id: "whatsapp_business", name: "WhatsApp Business", icon: "W", color: "#25D366", description: "Business messaging & automation", docsUrl: "https://business.whatsapp.com" },
] as const;

interface ConnectionRecord {
  id: string;
  provider: string;
  status: string;
  provider_account_name: string | null;
  connected_at: string | null;
  last_error: string | null;
}

type ConnectionStatus = "not_connected" | "pending" | "connected" | "expired" | "error";

export default function ConnectionsPage() {
  const [connections, setConnections] = useState<ConnectionRecord[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const res = await fetch("/api/portal/connections");
        if (res.ok) {
          const data = await res.json();
          setConnections(data.connections || []);
        }
      } catch { /* silent */ }
      setLoading(false);
    }
    load();
  }, []);

  function getStatus(providerId: string): { status: ConnectionStatus; record?: ConnectionRecord } {
    const record = connections.find((c) => c.provider === providerId);
    if (!record) return { status: "not_connected" };
    return { status: record.status as ConnectionStatus, record };
  }

  const connectedCount = connections.filter((c) => c.status === "connected").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Plug size={24} className="text-[#6C63FF]" />
          Connections
        </h1>
        <p className="text-sm text-[#6B7280] mt-1">
          Connect your business tools to power your automations.
          {connectedCount > 0 && (
            <span className="text-[#00D4AA] ml-1">
              {connectedCount} connected
            </span>
          )}
        </p>
      </div>

      {/* Info banner */}
      <div className="flex items-start gap-3 p-4 rounded-xl border border-[#6C63FF]/20 bg-[#6C63FF]/5">
        <Shield size={18} className="text-[#6C63FF] flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-[#B0B8C8]">
            Your credentials are encrypted and never shared. All connections use industry-standard OAuth 2.0. We only request the minimum permissions needed.
          </p>
        </div>
      </div>

      {/* Connection cards */}
      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl animate-pulse"
              style={{ background: "rgba(255,255,255,0.04)" }}
            />
          ))}
        </div>
      ) : (
        <div className="space-y-3">
          {PROVIDERS.map((provider) => {
            const { status, record } = getStatus(provider.id);
            return (
              <ConnectionCard
                key={provider.id}
                provider={provider}
                status={status}
                accountName={record?.provider_account_name}
                connectedAt={record?.connected_at}
                lastError={record?.last_error}
              />
            );
          })}
        </div>
      )}

      {/* Help section */}
      <div className="flex items-start gap-3 p-4 rounded-xl border border-white/[0.08] bg-white/[0.03]">
        <HelpCircle size={18} className="text-[#6B7280] flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-sm text-[#8B95A9] font-medium">Need help connecting?</p>
          <p className="text-xs text-[#6B7280] mt-0.5">
            Our team can assist with connecting your accounts. Email{" "}
            <a
              href="mailto:support@anyvisionmedia.com"
              className="text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
            >
              support@anyvisionmedia.com
            </a>{" "}
            or{" "}
            <a
              href="https://calendly.com/anyvisionmedia/onboarding"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
            >
              book a free setup call
            </a>
            .
          </p>
        </div>
      </div>
    </div>
  );
}
