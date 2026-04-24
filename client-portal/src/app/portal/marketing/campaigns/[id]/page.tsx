"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { CampaignStatusBadge } from "@/components/marketing/CampaignStatusBadge";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import { SpendProgressBar } from "@/components/marketing/SpendProgressBar";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";

interface Campaign {
  id: string;
  name: string;
  platform: string;
  campaign_type: string;
  status: string;
  budget_total: number;
  budget_daily: number;
  budget_spent: number;
  targeting: Record<string, unknown>;
  start_date: string | null;
  end_date: string | null;
  platform_campaign_id: string | null;
  notes: string | null;
  created_at: string;
}

interface Ad {
  id: string;
  name: string;
  ad_type: string;
  status: string;
  headline: string | null;
  primary_text: string | null;
  performance: Record<string, number> | null;
}

interface PerfDay {
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  leads: number;
  ctr: number;
  cpc: number;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

export default function CampaignDetailPage() {
  const { id } = useParams<{ id: string }>();
  const supabase = createClient();
  const [campaign, setCampaign] = useState<Campaign | null>(null);
  const [ads, setAds] = useState<Ad[]>([]);
  const [perf, setPerf] = useState<PerfDay[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [campRes, adsRes, perfRes] = await Promise.all([
        supabase.from("mkt_campaigns").select("*").eq("id", id).single(),
        supabase.from("mkt_ads").select("*").eq("campaign_id", id).order("created_at", { ascending: false }),
        supabase.rpc("mkt_get_campaign_performance", { p_campaign_id: id, p_days: 30 }),
      ]);

      if (campRes.data) setCampaign(campRes.data);
      if (adsRes.data) setAds(adsRes.data);
      if (perfRes.data) setPerf(Array.isArray(perfRes.data) ? perfRes.data : []);
      setLoading(false);
    }

    load();
  }, [supabase, id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-[#6B7280]">Loading campaign...</p>
      </div>
    );
  }

  if (!campaign) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-[#6B7280]">Campaign not found</p>
      </div>
    );
  }

  const totalImpressions = perf.reduce((s, d) => s + d.impressions, 0);
  const totalClicks = perf.reduce((s, d) => s + d.clicks, 0);
  const totalSpend = perf.reduce((s, d) => s + d.spend, 0);
  const totalConversions = perf.reduce((s, d) => s + d.conversions, 0);
  const totalLeads = perf.reduce((s, d) => s + d.leads, 0);

  return (
    <div className="space-y-6">
      {/* Back + Header */}
      <div className="flex items-start gap-4">
        <Link
          href="/portal/marketing/campaigns"
          className="mt-1 grid place-items-center size-8 rounded-[var(--radius-sm)] text-[var(--text-muted)] hover:text-foreground hover:bg-[var(--bg-card-hover)] transition-colors"
          aria-label="Back to campaigns"
        >
          <ArrowLeft className="size-4" />
        </Link>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 min-w-0">
            <PlatformIcon platform={campaign.platform} size={32} />
            <div className="min-w-0">
              <h1 className="text-2xl font-bold text-foreground tracking-tight truncate">
                {campaign.name}
              </h1>
              <p className="text-sm text-[var(--text-muted)] capitalize mt-0.5">
                {campaign.campaign_type.replace("_", " ")}
                {campaign.platform_campaign_id && (
                  <span> · ID: {campaign.platform_campaign_id}</span>
                )}
              </p>
            </div>
          </div>
        </div>
        <CampaignStatusBadge status={campaign.status} />
      </div>

      {/* Budget + Dates */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <h3 className="text-sm font-medium text-[#B0B8C8] mb-3">Budget</h3>
            <SpendProgressBar
              spent={campaign.budget_spent}
              budget={campaign.budget_total}
              label="Total Budget"
            />
            {campaign.budget_daily > 0 && (
              <p className="text-xs text-[#6B7280] mt-2">
                Daily limit: {formatZAR(campaign.budget_daily)}
              </p>
            )}
          </div>
          <div>
            <h3 className="text-sm font-medium text-[#B0B8C8] mb-3">Schedule</h3>
            <div className="space-y-1 text-sm text-[#B0B8C8]">
              <p>Start: {campaign.start_date ? new Date(campaign.start_date).toLocaleDateString("en-ZA") : "Not set"}</p>
              <p>End: {campaign.end_date ? new Date(campaign.end_date).toLocaleDateString("en-ZA") : "Ongoing"}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Performance Summary (30 days) */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6">
        <h3 className="text-sm font-medium text-[#B0B8C8] mb-4">Performance (Last 30 Days)</h3>
        {perf.length === 0 ? (
          <p className="text-sm text-[#6B7280]">No performance data yet</p>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              { label: "Impressions", value: totalImpressions.toLocaleString() },
              { label: "Clicks", value: totalClicks.toLocaleString() },
              { label: "Spend", value: formatZAR(totalSpend) },
              { label: "Conversions", value: totalConversions.toLocaleString() },
              { label: "Leads", value: totalLeads.toLocaleString() },
            ].map((m) => (
              <div key={m.label} className="p-3 rounded-lg bg-[rgba(255,255,255,0.03)]">
                <p className="text-xs text-[#6B7280]">{m.label}</p>
                <p className="text-lg font-semibold text-white mt-1">{m.value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Ads Table */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6">
        <h3 className="text-sm font-medium text-[#B0B8C8] mb-4">
          Ads ({ads.length})
        </h3>
        {ads.length === 0 ? (
          <p className="text-sm text-[#6B7280]">No ads created for this campaign</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)]">
                  <th className="text-left px-3 py-2 text-[#6B7280] font-medium">Ad Name</th>
                  <th className="text-left px-3 py-2 text-[#6B7280] font-medium">Type</th>
                  <th className="text-left px-3 py-2 text-[#6B7280] font-medium">Status</th>
                  <th className="text-left px-3 py-2 text-[#6B7280] font-medium">Headline</th>
                </tr>
              </thead>
              <tbody>
                {ads.map((ad) => (
                  <tr
                    key={ad.id}
                    className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)]"
                  >
                    <td className="px-3 py-2 text-white font-medium">{ad.name}</td>
                    <td className="px-3 py-2 text-[#B0B8C8] capitalize">{ad.ad_type}</td>
                    <td className="px-3 py-2">
                      <CampaignStatusBadge status={ad.status} />
                    </td>
                    <td className="px-3 py-2 text-[#B0B8C8] max-w-[200px] truncate">
                      {ad.headline ?? "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Notes */}
      {campaign.notes && (
        <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] p-6">
          <h3 className="text-sm font-medium text-[#B0B8C8] mb-2">Notes</h3>
          <p className="text-sm text-[#B0B8C8] whitespace-pre-wrap">{campaign.notes}</p>
        </div>
      )}
    </div>
  );
}
