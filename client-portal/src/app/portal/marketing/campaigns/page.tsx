"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { CampaignStatusBadge } from "@/components/marketing/CampaignStatusBadge";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import { SpendProgressBar } from "@/components/marketing/SpendProgressBar";
import Link from "next/link";
import { Plus, Filter } from "lucide-react";

interface Campaign {
  id: string;
  name: string;
  platform: string;
  campaign_type: string;
  status: string;
  budget_total: number;
  budget_daily: number;
  budget_spent: number;
  start_date: string | null;
  end_date: string | null;
  performance_summary: Record<string, number> | null;
  created_at: string;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

const STATUS_OPTIONS = [
  { value: "", label: "All Statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "paused", label: "Paused" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
];

const PLATFORM_OPTIONS = [
  { value: "", label: "All Platforms" },
  { value: "google_ads", label: "Google Ads" },
  { value: "meta_ads", label: "Meta Ads" },
  { value: "tiktok_ads", label: "TikTok Ads" },
  { value: "linkedin_ads", label: "LinkedIn Ads" },
  { value: "multi_platform", label: "Multi-Platform" },
];

export default function CampaignsPage() {
  const supabase = createClient();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [platformFilter, setPlatformFilter] = useState("");

  useEffect(() => {
    async function load() {
      setLoading(true);
      let query = supabase
        .from("mkt_campaigns")
        .select("*")
        .order("created_at", { ascending: false });

      if (statusFilter) query = query.eq("status", statusFilter);
      if (platformFilter) query = query.eq("platform", platformFilter);

      const { data } = await query;
      setCampaigns(data ?? []);
      setLoading(false);
    }

    load();
  }, [supabase, statusFilter, platformFilter]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Campaigns</h1>
          <p className="text-sm text-[#B0B8C8] mt-1">{campaigns.length} campaigns</p>
        </div>
        <Link
          href="/portal/marketing/campaigns/new"
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-all"
          style={{
            background: "linear-gradient(135deg, #10B981, #059669)",
          }}
        >
          <Plus size={16} />
          New Campaign
        </Link>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Filter size={16} className="text-[#6B7280]" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981]"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="px-3 py-1.5 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981]"
        >
          {PLATFORM_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Campaign Table */}
      <div className="floating-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left px-4 py-3 text-[#6B7280] font-medium">Campaign</th>
                <th className="text-left px-4 py-3 text-[#6B7280] font-medium">Platform</th>
                <th className="text-left px-4 py-3 text-[#6B7280] font-medium">Status</th>
                <th className="text-left px-4 py-3 text-[#6B7280] font-medium">Budget</th>
                <th className="text-left px-4 py-3 text-[#6B7280] font-medium">Dates</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-[#6B7280]">
                    Loading campaigns...
                  </td>
                </tr>
              ) : campaigns.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-[#6B7280]">
                    No campaigns found. Create your first campaign to get started.
                  </td>
                </tr>
              ) : (
                campaigns.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/portal/marketing/campaigns/${c.id}`}
                        className="text-white hover:text-[#10B981] font-medium transition-colors"
                      >
                        {c.name}
                      </Link>
                      <p className="text-xs text-[#6B7280] mt-0.5 capitalize">
                        {c.campaign_type.replace("_", " ")}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <PlatformIcon platform={c.platform} size={28} />
                    </td>
                    <td className="px-4 py-3">
                      <CampaignStatusBadge status={c.status} />
                    </td>
                    <td className="px-4 py-3 min-w-[180px]">
                      <SpendProgressBar
                        spent={c.budget_spent}
                        budget={c.budget_total}
                      />
                      <p className="text-xs text-[#6B7280] mt-1">
                        {formatZAR(c.budget_spent)} / {formatZAR(c.budget_total)}
                        {c.budget_daily > 0 && (
                          <span> &middot; {formatZAR(c.budget_daily)}/day</span>
                        )}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-[#B0B8C8]">
                      {c.start_date ? (
                        <span className="text-xs">
                          {new Date(c.start_date).toLocaleDateString("en-ZA")}
                          {c.end_date && (
                            <> &rarr; {new Date(c.end_date).toLocaleDateString("en-ZA")}</>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-[#6B7280]">Not set</span>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
