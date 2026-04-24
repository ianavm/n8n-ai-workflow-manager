"use client";

import { useEffect, useState } from "react";
import { HelpCircle, Shield } from "lucide-react";

import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";
import { ConnectionCard } from "@/components/connections/ConnectionCard";

const PROVIDERS = [
  { id: "google_ads",        name: "Google Ads",        icon: "G", color: "#4285F4", description: "Search & display advertising campaigns",         docsUrl: "https://ads.google.com" },
  { id: "meta_ads",          name: "Meta Ads",          icon: "M", color: "#0668E1", description: "Facebook & Instagram advertising",                docsUrl: "https://business.facebook.com" },
  { id: "quickbooks",        name: "QuickBooks",        icon: "Q", color: "#2CA01C", description: "Accounting, invoicing & reconciliation",          docsUrl: "https://quickbooks.intuit.com" },
  { id: "google_workspace",  name: "Google Workspace",  icon: "W", color: "#EA4335", description: "Gmail, Sheets, Drive & Calendar",                 docsUrl: "https://workspace.google.com" },
  { id: "tiktok_ads",        name: "TikTok Ads",        icon: "T", color: "#000000", description: "Short-form video advertising",                    docsUrl: "https://ads.tiktok.com" },
  { id: "linkedin_ads",      name: "LinkedIn Ads",      icon: "L", color: "#0A66C2", description: "B2B professional advertising",                    docsUrl: "https://www.linkedin.com/campaignmanager" },
  { id: "whatsapp_business", name: "WhatsApp Business", icon: "W", color: "#25D366", description: "Business messaging & automation",                 docsUrl: "https://business.whatsapp.com" },
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
      } catch {
        /* silent */
      } finally {
        setLoading(false);
      }
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
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Operations"
        title="Connections"
        description="Connect your business tools to power your automations."
        actions={
          connectedCount > 0 ? (
            <Badge tone="success" appearance="soft">
              {connectedCount} connected
            </Badge>
          ) : null
        }
      />

      {/* Security banner */}
      <Card variant="default" padding="md">
        <div className="flex items-start gap-3">
          <span className="grid place-items-center size-10 rounded-full bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)] shrink-0">
            <Shield className="size-4" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">Your credentials are safe</p>
            <p className="text-sm text-[var(--text-muted)] mt-0.5 leading-relaxed">
              All connections use industry-standard OAuth 2.0 with encryption at rest. We only
              request the minimum permissions needed — credentials are never shared.
            </p>
          </div>
        </div>
      </Card>

      {/* Provider list */}
      {loading ? (
        <LoadingState variant="list" rows={4} />
      ) : (
        <div className="flex flex-col gap-3">
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

      {/* Help */}
      <Card variant="default" padding="md">
        <div className="flex items-start gap-3">
          <span className="grid place-items-center size-10 rounded-full bg-[var(--bg-card-hover)] text-[var(--text-muted)] shrink-0">
            <HelpCircle className="size-4" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">Need help connecting?</p>
            <p className="text-sm text-[var(--text-muted)] mt-0.5 leading-relaxed">
              Email{" "}
              <a
                href="mailto:support@anyvisionmedia.com"
                className="font-medium text-[var(--brand-primary)] hover:underline"
              >
                support@anyvisionmedia.com
              </a>{" "}
              or{" "}
              <a
                href="https://calendly.com/anyvisionmedia/onboarding"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-[var(--brand-primary)] hover:underline"
              >
                book a free setup call
              </a>
              .
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
