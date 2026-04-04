"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { StatCard } from "@/components/charts/StatCard";
import { CampaignStatusBadge } from "@/components/marketing/CampaignStatusBadge";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import {
  DollarSign,
  Users,
  Target,
  TrendingUp,
  BarChart3,
  Percent,
} from "lucide-react";

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

interface Campaign {
  id: string;
  name: string;
  platform: string;
  status: string;
  budget_spent: number;
  budget_total: number;
}

interface Lead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  source: string;
  stage: string;
  created_at: string;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export default function MarketingDashboard() {
  const supabase = createClient();
  const [kpis, setKpis] = useState<DashboardKPIs | null>(null);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const [kpiRes, campRes, leadRes] = await Promise.all([
        fetch("/api/portal/marketing/dashboard"),
        supabase
          .from("mkt_campaigns")
          .select("id, name, platform, status, budget_spent, budget_total")
          .in("status", ["active", "paused"])
          .order("budget_spent", { ascending: false })
          .limit(5),
        supabase
          .from("mkt_leads")
          .select("id, first_name, last_name, email, source, stage, created_at")
          .order("created_at", { ascending: false })
          .limit(5),
      ]);

      if (kpiRes.ok) {
        const data = await kpiRes.json();
        setKpis(data);
      }
      if (campRes.data) setCampaigns(campRes.data);
      if (leadRes.data) setLeads(leadRes.data);
      setLoading(false);
    }

    load();
  }, [supabase]);

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Marketing Dashboard</h1>
        <p className="text-sm text-[#B0B8C8] mt-1">
          Campaign performance, leads, and content overview
        </p>
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

      {/* Bottom row: Top Campaigns + Recent Leads */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Campaigns */}
        <div className="floating-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Top Campaigns</h2>
          {campaigns.length === 0 && !loading ? (
            <p className="text-sm text-[#6B7280]">No active campaigns yet</p>
          ) : (
            <div className="space-y-3">
              {campaigns.map((c) => (
                <div
                  key={c.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <PlatformIcon platform={c.platform} />
                    <div>
                      <p className="text-sm font-medium text-white">{c.name}</p>
                      <p className="text-xs text-[#6B7280]">
                        {formatZAR(c.budget_spent)} spent of {formatZAR(c.budget_total)}
                      </p>
                    </div>
                  </div>
                  <CampaignStatusBadge status={c.status} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Leads */}
        <div className="floating-card p-6">
          <h2 className="text-base font-semibold text-white mb-4">Recent Leads</h2>
          {leads.length === 0 && !loading ? (
            <p className="text-sm text-[#6B7280]">No leads captured yet</p>
          ) : (
            <div className="space-y-3">
              {leads.map((l) => (
                <div
                  key={l.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
                >
                  <div>
                    <p className="text-sm font-medium text-white">
                      {[l.first_name, l.last_name].filter(Boolean).join(" ") || l.email || "Unknown"}
                    </p>
                    <p className="text-xs text-[#6B7280]">
                      {l.source.replace("_", " ")} &middot; {l.stage}
                    </p>
                  </div>
                  <span className="text-xs text-[#6B7280]">
                    {new Date(l.created_at).toLocaleDateString("en-ZA")}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
