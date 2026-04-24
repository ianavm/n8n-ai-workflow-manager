"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { Plus, Filter } from "lucide-react";

import { CampaignStatusBadge } from "@/components/marketing/CampaignStatusBadge";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import { SpendProgressBar } from "@/components/marketing/SpendProgressBar";
import { PageHeader } from "@/components/portal/PageHeader";
import { Button } from "@/components/ui-shadcn/button";

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
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Marketing"
        title="Campaigns"
        description={`${campaigns.length} ${campaigns.length === 1 ? "campaign" : "campaigns"} across all platforms.`}
        actions={
          <Button asChild variant="default" size="md">
            <Link href="/portal/marketing/campaigns/new">
              <Plus className="size-4" />
              New campaign
            </Link>
          </Button>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-3">
        <Filter className="size-4 text-[var(--text-dim)]" />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="h-9 px-3 rounded-[var(--radius-sm)] text-sm bg-[var(--input)] border border-[var(--border-subtle)] text-foreground focus:outline-none focus:border-[var(--accent-teal)]"
        >
          {STATUS_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
        <select
          value={platformFilter}
          onChange={(e) => setPlatformFilter(e.target.value)}
          className="h-9 px-3 rounded-[var(--radius-sm)] text-sm bg-[var(--input)] border border-[var(--border-subtle)] text-foreground focus:outline-none focus:border-[var(--accent-teal)]"
        >
          {PLATFORM_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>{o.label}</option>
          ))}
        </select>
      </div>

      {/* Campaign Table */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--border-subtle)] bg-[var(--bg-card)] overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[var(--border-subtle)]">
                <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">Campaign</th>
                <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">Platform</th>
                <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">Status</th>
                <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">Budget</th>
                <th className="text-left px-4 py-3 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)]">Dates</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-[var(--text-muted)]">
                    Loading campaigns...
                  </td>
                </tr>
              ) : campaigns.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-[var(--text-muted)]">
                    No campaigns found. Create your first campaign to get started.
                  </td>
                </tr>
              ) : (
                campaigns.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-card-hover)] transition-colors"
                  >
                    <td className="px-4 py-3">
                      <Link
                        href={`/portal/marketing/campaigns/${c.id}`}
                        className="text-foreground hover:text-[var(--accent-teal)] font-semibold transition-colors"
                      >
                        {c.name}
                      </Link>
                      <p className="text-xs text-[var(--text-dim)] mt-0.5 capitalize">
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
                      <p className="text-xs text-[var(--text-dim)] mt-1">
                        {formatZAR(c.budget_spent)} / {formatZAR(c.budget_total)}
                        {c.budget_daily > 0 && (
                          <span> &middot; {formatZAR(c.budget_daily)}/day</span>
                        )}
                      </p>
                    </td>
                    <td className="px-4 py-3 text-[var(--text-muted)]">
                      {c.start_date ? (
                        <span className="text-xs">
                          {new Date(c.start_date).toLocaleDateString("en-ZA")}
                          {c.end_date && (
                            <> → {new Date(c.end_date).toLocaleDateString("en-ZA")}</>
                          )}
                        </span>
                      ) : (
                        <span className="text-xs text-[var(--text-dim)]">Not set</span>
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
