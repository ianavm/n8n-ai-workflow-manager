"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { StatCard } from "@/components/charts/StatCard";
import {
  DollarSign,
  Users,
  Target,
  BarChart3,
  TrendingUp,
  Percent,
  ArrowLeft,
  Settings,
  Check,
  X,
} from "lucide-react";

interface MktConfig {
  id: string;
  client_id: string;
  company_name: string | null;
  industry: string | null;
  platforms_enabled: string[];
  budget_monthly_cap: number;
  budget_alert_threshold: number;
  ad_platform_config: Record<string, unknown>;
  n8n_credentials: Record<string, unknown>;
  content_config: {
    auto_approve?: boolean;
    ai_model?: string;
    posting_times?: Record<string, string>;
  };
  lead_assignment_mode: string;
  modules_enabled: Record<string, boolean>;
  created_at: string;
  updated_at: string;
  client_name?: string;
}

interface DashboardKPIs {
  total_spend_month: number;
  leads_generated_month: number;
  leads_generated_today: number;
  active_campaigns: number;
  avg_cpl: number;
  avg_cpa: number;
  total_roas: number;
  conversion_rate: number;
  scheduled_posts: number;
  pipeline_value: number;
  open_tasks: number;
  unread_conversations: number;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

const PLATFORM_LABELS: Record<string, string> = {
  google_ads: "Google Ads",
  meta_ads: "Meta Ads",
  tiktok_ads: "TikTok Ads",
  linkedin_ads: "LinkedIn Ads",
  blotato: "Blotato",
};

const MODULE_LABELS: Record<string, string> = {
  campaigns: "Campaigns",
  content: "Content",
  leads: "Leads",
  conversations: "Conversations",
  reports: "Reports",
};

export default function ClientMarketingDetail() {
  const params = useParams();
  const clientId = params.id as string;

  const [config, setConfig] = useState<MktConfig | null>(null);
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [configRes, kpiRes] = await Promise.all([
        fetch(`/api/admin/marketing/config/${clientId}`),
        fetch(`/api/admin/marketing/overview?client_kpis=${clientId}`),
      ]);

      if (!configRes.ok) {
        const body = await configRes.json().catch(() => ({ error: "Not found" }));
        throw new Error(body.error ?? `HTTP ${configRes.status}`);
      }

      const configJson = await configRes.json();
      setConfig(configJson.data);

      if (kpiRes.ok) {
        const kpiJson = await kpiRes.json();
        setKpis(kpiJson.data);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load client");
    } finally {
      setLoading(false);
    }
  }, [clientId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="space-y-4">
        <Link href="/admin/marketing/clients" className="flex items-center gap-2 text-sm text-[#B0B8C8] hover:text-white">
          <ArrowLeft size={16} /> Back to Clients
        </Link>
        <div className="floating-card p-6 text-center">
          <p className="text-red-400">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Back + Header */}
      <div className="flex items-center justify-between">
        <div>
          <Link
            href="/admin/marketing"
            className="flex items-center gap-2 text-sm text-[#B0B8C8] hover:text-white mb-2"
          >
            <ArrowLeft size={16} /> Back to Overview
          </Link>
          <h1 className="text-2xl font-bold text-white">
            {loading ? "Loading..." : config?.client_name ?? config?.company_name ?? "Client Marketing"}
          </h1>
          {config?.industry && (
            <p className="text-sm text-[#6B7280] mt-1">{config.industry}</p>
          )}
        </div>
        <button
          disabled
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.3)] opacity-50 cursor-not-allowed"
        >
          <Settings size={16} />
          Edit Config
        </button>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <StatCard
          title="Ad Spend (Month)"
          value={kpis ? formatZAR(kpis.total_spend_month) : "..."}
          icon={<DollarSign size={22} />}
          color="coral"
          loading={loading}
        />
        <StatCard
          title="Leads Generated"
          value={kpis?.leads_generated_month ?? 0}
          icon={<Users size={22} />}
          color="teal"
          loading={loading}
        />
        <StatCard
          title="Avg CPL"
          value={kpis ? formatZAR(kpis.avg_cpl) : "..."}
          icon={<Target size={22} />}
          color="purple"
          loading={loading}
        />
        <StatCard
          title="Active Campaigns"
          value={kpis?.active_campaigns ?? 0}
          icon={<BarChart3 size={22} />}
          color="amber"
          loading={loading}
        />
        <StatCard
          title="ROAS"
          value={kpis ? `${kpis.total_roas}x` : "..."}
          icon={<TrendingUp size={22} />}
          color="teal"
          loading={loading}
        />
        <StatCard
          title="Conv. Rate"
          value={kpis ? `${kpis.conversion_rate}%` : "..."}
          icon={<Percent size={22} />}
          color="purple"
          loading={loading}
        />
      </div>

      {/* Config Summary */}
      {config && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Platforms & Budget */}
          <div className="floating-card p-6 space-y-5">
            <h2 className="text-base font-semibold text-white">Configuration</h2>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Platforms Enabled
              </p>
              <div className="flex flex-wrap gap-2">
                {config.platforms_enabled.length === 0 ? (
                  <span className="text-sm text-[#6B7280]">None</span>
                ) : (
                  config.platforms_enabled.map((p) => (
                    <span
                      key={p}
                      className="px-3 py-1 rounded-full text-xs font-medium bg-[rgba(16,185,129,0.1)] text-[#10B981]"
                    >
                      {PLATFORM_LABELS[p] ?? p}
                    </span>
                  ))
                )}
              </div>
            </div>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Monthly Budget Cap
              </p>
              <p className="text-sm text-white">
                {config.budget_monthly_cap > 0
                  ? formatZAR(config.budget_monthly_cap)
                  : "No cap set"}
              </p>
            </div>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Alert Threshold
              </p>
              <p className="text-sm text-white">
                {Math.round(config.budget_alert_threshold * 100)}% of budget
              </p>
            </div>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Lead Assignment
              </p>
              <p className="text-sm text-white capitalize">
                {config.lead_assignment_mode.replace(/_/g, " ")}
              </p>
            </div>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                AI Model
              </p>
              <p className="text-sm text-white font-mono text-xs">
                {config.content_config?.ai_model ?? "Default"}
              </p>
            </div>

            <div>
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Auto-Approve Content
              </p>
              <p className="text-sm text-white">
                {config.content_config?.auto_approve ? "Yes" : "No"}
              </p>
            </div>
          </div>

          {/* Modules & Metadata */}
          <div className="floating-card p-6 space-y-5">
            <h2 className="text-base font-semibold text-white">Modules</h2>

            <div className="space-y-2">
              {Object.entries(config.modules_enabled).map(([key, enabled]) => (
                <div
                  key={key}
                  className="flex items-center justify-between py-2 px-3 rounded-lg bg-[rgba(255,255,255,0.02)]"
                >
                  <span className="text-sm text-[#B0B8C8]">
                    {MODULE_LABELS[key] ?? key}
                  </span>
                  {enabled ? (
                    <span className="flex items-center gap-1 text-xs text-[#10B981]">
                      <Check size={14} /> Enabled
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-xs text-[#6B7280]">
                      <X size={14} /> Disabled
                    </span>
                  )}
                </div>
              ))}
            </div>

            <div className="pt-4 border-t border-[rgba(255,255,255,0.06)]">
              <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                Additional KPIs
              </p>
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-lg bg-[rgba(255,255,255,0.02)]">
                  <p className="text-xs text-[#6B7280]">Scheduled Posts</p>
                  <p className="text-lg font-semibold text-white">
                    {kpis?.scheduled_posts ?? 0}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[rgba(255,255,255,0.02)]">
                  <p className="text-xs text-[#6B7280]">Open Tasks</p>
                  <p className="text-lg font-semibold text-white">
                    {kpis?.open_tasks ?? 0}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[rgba(255,255,255,0.02)]">
                  <p className="text-xs text-[#6B7280]">Pipeline Value</p>
                  <p className="text-lg font-semibold text-white">
                    {kpis ? formatZAR(kpis.pipeline_value) : "..."}
                  </p>
                </div>
                <div className="p-3 rounded-lg bg-[rgba(255,255,255,0.02)]">
                  <p className="text-xs text-[#6B7280]">Unread Messages</p>
                  <p className="text-lg font-semibold text-white">
                    {kpis?.unread_conversations ?? 0}
                  </p>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-[rgba(255,255,255,0.06)] text-xs text-[#6B7280]">
              <p>Created: {new Date(config.created_at).toLocaleDateString("en-ZA")}</p>
              <p>Updated: {new Date(config.updated_at).toLocaleDateString("en-ZA")}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
