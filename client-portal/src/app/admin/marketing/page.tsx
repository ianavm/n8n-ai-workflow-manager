"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { StatCard } from "@/components/charts/StatCard";
import {
  DollarSign,
  Users,
  Target,
  BarChart3,
  AlertTriangle,
  Clock,
  XCircle,
} from "lucide-react";

interface OverviewData {
  total_spend_month: number;
  total_leads_month: number;
  avg_cpl: number;
  active_campaigns: number;
  clients: ClientRow[];
  alerts: Alert[];
}

interface ClientRow {
  client_id: string;
  client_name: string;
  total_spend: number;
  leads: number;
  cpl: number;
  active_campaigns: number;
  budget_monthly_cap: number;
  budget_usage_pct: number;
  has_config: boolean;
}

interface Alert {
  type: "budget_warning" | "failed_posts" | "stale_leads";
  client_name: string;
  client_id: string;
  message: string;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

const ALERT_STYLES: Record<string, { icon: typeof AlertTriangle; color: string; bg: string }> = {
  budget_warning: { icon: AlertTriangle, color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
  failed_posts: { icon: XCircle, color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
  stale_leads: { icon: Clock, color: "#6B7280", bg: "rgba(107,114,128,0.1)" },
};

export default function MarketingAdminOverview() {
  const [data, setData] = useState<OverviewData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/marketing/overview");
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(body.error ?? `HTTP ${res.status}`);
      }
      const json = await res.json();
      setData(json.data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load overview");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <div className="floating-card p-6 text-center">
        <p className="text-red-400">{error}</p>
        <button
          onClick={() => { setError(null); setLoading(true); load(); }}
          className="mt-3 text-sm text-[#10B981] hover:underline"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Marketing Overview</h1>
        <p className="text-sm text-[var(--text-muted)] mt-1">
          Cross-client marketing performance at a glance
        </p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Total Ad Spend (Month)"
          value={data ? formatZAR(data.total_spend_month) : "..."}
          icon={<DollarSign size={22} />}
          color="coral"
          loading={loading}
        />
        <StatCard
          title="Total Leads (Month)"
          value={data?.total_leads_month ?? 0}
          icon={<Users size={22} />}
          color="teal"
          loading={loading}
        />
        <StatCard
          title="Avg CPL"
          value={data ? formatZAR(data.avg_cpl) : "..."}
          icon={<Target size={22} />}
          color="purple"
          loading={loading}
        />
        <StatCard
          title="Active Campaigns"
          value={data?.active_campaigns ?? 0}
          icon={<BarChart3 size={22} />}
          color="amber"
          loading={loading}
        />
      </div>

      {/* Client Ranking Table */}
      <div className="floating-card overflow-hidden">
        <div className="p-5 border-b border-[rgba(255,255,255,0.06)]">
          <h2 className="text-base font-semibold text-white">Client Rankings</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[var(--text-dim)] text-xs uppercase tracking-wider border-b border-[rgba(255,255,255,0.04)]">
                <th className="px-5 py-3">Client</th>
                <th className="px-5 py-3">Spend (Month)</th>
                <th className="px-5 py-3">Leads</th>
                <th className="px-5 py-3">CPL</th>
                <th className="px-5 py-3">Active Campaigns</th>
                <th className="px-5 py-3">Budget Usage</th>
                <th className="px-5 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                Array.from({ length: 4 }).map((_, i) => (
                  <tr key={i} className="border-b border-[rgba(255,255,255,0.04)]">
                    {Array.from({ length: 7 }).map((_, j) => (
                      <td key={j} className="px-5 py-3">
                        <div className="h-4 w-16 rounded bg-[rgba(255,255,255,0.04)] animate-pulse" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : data?.clients.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-8 text-center text-[var(--text-dim)]">
                    No clients with marketing configured yet.{" "}
                    <Link href="/admin/marketing/onboarding" className="text-[#10B981] hover:underline">
                      Onboard a client
                    </Link>
                  </td>
                </tr>
              ) : (
                data?.clients.map((client) => (
                  <tr
                    key={client.client_id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <td className="px-5 py-3">
                      <Link
                        href={`/admin/marketing/clients/${client.client_id}`}
                        className="text-white font-medium hover:text-[#10B981] transition-colors"
                      >
                        {client.client_name}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-white">{formatZAR(client.total_spend)}</td>
                    <td className="px-5 py-3 text-white">{client.leads}</td>
                    <td className="px-5 py-3 text-white">
                      {client.leads > 0 ? formatZAR(client.cpl) : "--"}
                    </td>
                    <td className="px-5 py-3 text-white">{client.active_campaigns}</td>
                    <td className="px-5 py-3">
                      {client.budget_monthly_cap > 0 ? (
                        <div className="flex items-center gap-2">
                          <div className="flex-1 h-2 rounded-full bg-[rgba(255,255,255,0.06)] max-w-[100px]">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${Math.min(client.budget_usage_pct, 100)}%`,
                                backgroundColor:
                                  client.budget_usage_pct >= 90
                                    ? "#EF4444"
                                    : client.budget_usage_pct >= 80
                                      ? "#F59E0B"
                                      : "#10B981",
                              }}
                            />
                          </div>
                          <span className="text-xs text-[var(--text-dim)]">
                            {Math.round(client.budget_usage_pct)}%
                          </span>
                        </div>
                      ) : (
                        <span className="text-xs text-[var(--text-dim)]">No cap</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${
                          client.active_campaigns > 0
                            ? "bg-[rgba(16,185,129,0.1)] text-[#10B981]"
                            : "bg-[rgba(107,114,128,0.1)] text-[var(--text-dim)]"
                        }`}
                      >
                        {client.active_campaigns > 0 ? "Active" : "Config Only"}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Alerts */}
      {data && data.alerts.length > 0 && (
        <div className="floating-card p-5">
          <h2 className="text-base font-semibold text-white mb-4">Alerts</h2>
          <div className="space-y-3">
            {data.alerts.map((alert, i) => {
              const style = ALERT_STYLES[alert.type] ?? ALERT_STYLES.stale_leads;
              const AlertIcon = style.icon;
              return (
                <Link
                  key={`${alert.client_id}-${alert.type}-${i}`}
                  href={`/admin/marketing/clients/${alert.client_id}`}
                  className="flex items-center gap-3 p-3 rounded-lg hover:bg-[rgba(255,255,255,0.03)] transition-colors"
                >
                  <div
                    className="rounded-full p-2"
                    style={{ backgroundColor: style.bg }}
                  >
                    <AlertIcon size={14} style={{ color: style.color }} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white font-medium">{alert.client_name}</p>
                    <p className="text-xs text-[var(--text-dim)]">{alert.message}</p>
                  </div>
                </Link>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
