"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { Skeleton } from "@/components/ui/Skeleton";
import { format } from "date-fns";
import { toast } from "sonner";
import {
  Users,
  CheckCircle,
  MessageSquare,
  UserPlus,
  AlertTriangle,
  TrendingUp,
  Activity,
  Zap,
  Server,
  Database,
  Cloud,
} from "lucide-react";
import Link from "next/link";

interface ClientSummary {
  id: string;
  full_name: string;
  email: string;
  company_name: string | null;
  status: string;
  last_login_at: string | null;
  active_workflows: number;
  messages_sent: number;
  messages_received: number;
  leads_created: number;
  total_crashes: number;
}

interface GlobalStats {
  totalClients: number;
  activeClients: number;
  totalMessages: number;
  totalLeads: number;
  totalCrashes: number;
}

// Reusable floating stat card for the bento grid
function BentoStat({
  icon,
  iconBg,
  iconColor,
  value,
  label,
  change,
  changeDir,
  className = "",
}: {
  icon: React.ReactNode;
  iconBg: string;
  iconColor: string;
  value: string | number;
  label: string;
  change?: string;
  changeDir?: "up" | "down";
  className?: string;
}) {
  return (
    <div className={`floating-card p-6 ${className}`}>
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
        style={{ background: iconBg, color: iconColor }}
      >
        {icon}
      </div>
      <div className="stat-number-shimmer mb-1.5">
        {typeof value === "number" ? value.toLocaleString() : value}
      </div>
      <div className="text-sm text-[#B0B8C8]">{label}</div>
      {change && (
        <span
          className={`inline-flex items-center gap-1 mt-2.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${
            changeDir === "up"
              ? "bg-[rgba(16,185,129,0.12)] text-[#10B981]"
              : "bg-[rgba(239,68,68,0.12)] text-[#EF4444]"
          }`}
        >
          {changeDir === "up" ? <TrendingUp size={12} /> : <AlertTriangle size={10} />}
          {change}
        </span>
      )}
    </div>
  );
}

export default function AdminDashboard() {
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [stats, setStats] = useState<GlobalStats>({
    totalClients: 0,
    activeClients: 0,
    totalMessages: 0,
    totalLeads: 0,
    totalCrashes: 0,
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      const res = await fetch("/api/admin/clients");
      if (res.ok) {
        const data: ClientSummary[] = await res.json();
        setClients(data);
        setStats({
          totalClients: data.length,
          activeClients: data.filter((c) => c.status === "active").length,
          totalMessages: data.reduce(
            (sum, c) => sum + c.messages_sent + c.messages_received,
            0
          ),
          totalLeads: data.reduce((sum, c) => sum + c.leads_created, 0),
          totalCrashes: data.reduce((sum, c) => sum + c.total_crashes, 0),
        });
      } else {
        toast.error("Failed to load client data");
      }
      setLoading(false);
    }
    fetchData();
  }, []);

  const flaggedClients = clients
    .filter((c) => c.total_crashes > 0)
    .sort((a, b) => b.total_crashes - a.total_crashes);

  const recentClients = [...clients]
    .sort((a, b) => {
      if (!a.last_login_at) return 1;
      if (!b.last_login_at) return -1;
      return new Date(b.last_login_at).getTime() - new Date(a.last_login_at).getTime();
    })
    .slice(0, 8);

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "suspended" ? "danger" : "warning";

  const today = new Date();
  const greeting =
    today.getHours() < 12
      ? "Good morning"
      : today.getHours() < 18
        ? "Good afternoon"
        : "Good evening";

  if (loading) {
    return (
      <div className="space-y-6 max-w-[1200px]">
        <Skeleton className="h-40 w-full rounded-2xl" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-36 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-0 max-w-[1200px]">
      {/* Bento Grid */}
      <div className="bento-grid">
        {/* ---- Row 1: Welcome Banner (4-col) + System Health (2-col) ---- */}

        {/* Welcome Banner */}
        <div className="col-4 animate-fade-in-up stagger-1">
          <div className="grad-border">
            <div className="grad-border-inner relative">
              {/* Animated blobs */}
              <div className="welcome-blob b1" />
              <div className="welcome-blob b2" />
              <div className="relative z-10">
                <h1 className="text-2xl font-bold text-white mb-1">
                  {greeting}, Ian
                </h1>
                <p className="text-sm text-[#B0B8C8]">
                  {format(today, "EEEE, d MMMM yyyy")}
                </p>
                <p className="text-[13px] text-[#6B7280] mt-3">
                  {stats.activeClients} clients active, {stats.totalCrashes === 0 ? "0 critical alerts" : `${stats.totalCrashes} errors detected`}
                </p>
                <div className="flex gap-2 mt-4 flex-wrap">
                  <span className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs bg-[rgba(255,255,255,0.06)] border border-[rgba(255,255,255,0.1)] text-[#B0B8C8]">
                    <span className="w-2 h-2 rounded-full bg-[#10B981] pulse-dot" />
                    All Systems Nominal
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* System Health */}
        <div className="col-2 floating-card p-5 animate-fade-in-up stagger-2">
          <div className="text-[13px] font-semibold text-white mb-4 flex items-center gap-2">
            <Server size={14} className="text-[#00D4AA]" />
            System Health
          </div>
          <div className="scrollable-section-sm space-y-1">
            {[
              { name: "n8n Cloud", pct: 99.98, icon: <Cloud size={12} /> },
              { name: "Supabase", pct: 100, icon: <Database size={12} /> },
              { name: "Airtable", pct: 99.91, icon: <Database size={12} /> },
              { name: "Xero", pct: 100, icon: <Zap size={12} /> },
            ].map((s) => (
              <div key={s.name} className="health-row">
                <span className="w-2 h-2 rounded-full bg-[#10B981] pulse-dot mr-2 flex-shrink-0" />
                <span className="text-[#B0B8C8] text-[13px] min-w-[80px]">{s.name}</span>
                <div className="health-bar">
                  <div className="health-fill" style={{ width: `${s.pct}%` }} />
                </div>
                <span className="text-[#00D4AA] font-semibold text-[13px] min-w-[52px] text-right">
                  {s.pct}%
                </span>
              </div>
            ))}
            <div className="text-center mt-3 text-xs text-[#6B7280]">
              Overall: <span className="text-[#00D4AA] font-bold">99.4%</span>
            </div>
          </div>
        </div>

        {/* ---- Row 2: Stat cards (2+2+2 with hero double-height) ---- */}

        <BentoStat
          className="col-2 animate-fade-in-up stagger-1"
          icon={<Users size={20} />}
          iconBg="rgba(108,99,255,0.1)"
          iconColor="#6C63FF"
          value={stats.totalClients}
          label="Total Clients"
          change="+14%"
          changeDir="up"
        />
        <BentoStat
          className="col-2 animate-fade-in-up stagger-2"
          icon={<CheckCircle size={20} />}
          iconBg="rgba(0,212,170,0.1)"
          iconColor="#00D4AA"
          value={stats.activeClients}
          label="Active Clients"
          change="+8%"
          changeDir="up"
        />

        {/* Hero stat: Total Messages (double height with sparkline) */}
        <div className="col-2 row-2 floating-card p-6 flex flex-col justify-between animate-fade-in-up stagger-3">
          <div>
            <div
              className="w-12 h-12 rounded-xl flex items-center justify-center mb-4"
              style={{ background: "rgba(108,99,255,0.1)", color: "#6C63FF" }}
            >
              <MessageSquare size={20} />
            </div>
            <div className="stat-number-shimmer" style={{ fontSize: 40 }}>
              {stats.totalMessages.toLocaleString()}
            </div>
            <div className="text-sm text-[#B0B8C8]">Total Messages</div>
            <span className="inline-flex items-center gap-1 mt-2.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[rgba(16,185,129,0.12)] text-[#10B981]">
              <TrendingUp size={12} /> +23%
            </span>
          </div>
          {/* Mini sparkline SVG */}
          <div className="mt-4">
            <svg viewBox="0 0 200 60" className="w-full h-[60px]" preserveAspectRatio="none">
              <defs>
                <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6C63FF" stopOpacity="0.3" />
                  <stop offset="100%" stopColor="#6C63FF" stopOpacity="0" />
                </linearGradient>
              </defs>
              <path d="M0,45 Q25,35 50,40 T100,30 T150,35 T200,20 V60 H0 Z" fill="url(#sparkGrad)" />
              <path d="M0,45 Q25,35 50,40 T100,30 T150,35 T200,20" fill="none" stroke="#6C63FF" strokeWidth="2" />
            </svg>
          </div>
        </div>

        <BentoStat
          className="col-2 animate-fade-in-up stagger-4"
          icon={<UserPlus size={20} />}
          iconBg="rgba(0,212,170,0.1)"
          iconColor="#00D4AA"
          value={stats.totalLeads}
          label="Total Leads"
          change="+45%"
          changeDir="up"
        />
        <BentoStat
          className="col-2 animate-fade-in-up stagger-5"
          icon={<AlertTriangle size={20} />}
          iconBg="rgba(239,68,68,0.1)"
          iconColor="#EF4444"
          value={stats.totalCrashes}
          label="Total Crashes"
          change={stats.totalCrashes > 0 ? `${stats.totalCrashes} errors` : "0 errors"}
          changeDir={stats.totalCrashes > 0 ? "down" : "up"}
        />

        {/* ---- Row 3: Activity Feed (4-col) + Needs Attention (2-col, BIGGER) ---- */}

        {/* Activity Feed */}
        <div className="col-4 glass-card p-6 animate-fade-in-up stagger-1">
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-white flex items-center gap-2">
              <Activity size={14} className="text-[#6C63FF]" />
              Recent Activity
            </div>
            <Link
              href="/admin/activity"
              className="text-xs text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
            >
              View all &rarr;
            </Link>
          </div>
          <div className="scrollable-section-sm">
            {recentClients.length === 0 ? (
              <p className="text-sm text-[#6B7280]">No recent activity</p>
            ) : (
              recentClients.map((c) => (
                <Link
                  key={c.id}
                  href={`/admin/clients/${c.id}`}
                  className="act-item"
                >
                  <div
                    className="act-dot"
                    style={{
                      background:
                        c.total_crashes > 0
                          ? "#EF4444"
                          : c.status === "active"
                            ? "#00D4AA"
                            : "#F59E0B",
                    }}
                  />
                  <span className="flex-1 text-[#B0B8C8]">
                    <span className="text-white font-medium">{c.full_name}</span>
                    {c.company_name ? ` (${c.company_name})` : ""}
                    {" — "}
                    {c.messages_received + c.messages_sent > 0
                      ? `${(c.messages_received + c.messages_sent).toLocaleString()} messages`
                      : "No messages yet"}
                  </span>
                  <span className="text-[11px] text-[#6B7280] flex-shrink-0">
                    {c.last_login_at
                      ? format(new Date(c.last_login_at), "MMM d")
                      : "Never"}
                  </span>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* Needs Attention — BIGGER card with scroll */}
        <div className="col-2 row-2 glass-card p-6 animate-fade-in-up stagger-2" style={{ borderLeft: "3px solid #EF4444" }}>
          <div className="flex items-center justify-between mb-4">
            <div className="text-sm font-semibold text-[#EF4444] flex items-center gap-2">
              <AlertTriangle size={14} />
              Needs Attention
            </div>
            <Link
              href="/admin/clients"
              className="text-xs text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
            >
              View all &rarr;
            </Link>
          </div>
          <div className="scrollable-section space-y-2">
            {flaggedClients.length === 0 ? (
              <div className="text-center py-8">
                <CheckCircle size={32} className="text-[#10B981] mx-auto mb-3 opacity-50" />
                <p className="text-sm text-[#6B7280]">All clients healthy</p>
                <p className="text-xs text-[#4B5563] mt-1">No crashes detected</p>
              </div>
            ) : (
              flaggedClients.map((c) => (
                <Link
                  key={c.id}
                  href={`/admin/clients/${c.id}`}
                  className="block px-4 py-3 rounded-xl bg-[rgba(239,68,68,0.05)] border border-[rgba(239,68,68,0.12)] hover:bg-[rgba(239,68,68,0.1)] hover:border-[rgba(239,68,68,0.25)] transition-all cursor-pointer"
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-white">{c.full_name}</span>
                    <span className="text-sm text-[#EF4444] font-semibold tabular-nums">
                      {c.total_crashes} {c.total_crashes === 1 ? "crash" : "crashes"}
                    </span>
                  </div>
                  {c.company_name && (
                    <span className="text-xs text-[#6B7280]">{c.company_name}</span>
                  )}
                  <div className="flex items-center gap-3 mt-2 text-xs text-[#6B7280]">
                    <span>{c.active_workflows} workflows</span>
                    <span>{(c.messages_sent + c.messages_received).toLocaleString()} msgs</span>
                    <span className="ml-auto">
                      <Badge variant="danger">{c.status}</Badge>
                    </span>
                  </div>
                </Link>
              ))
            )}
          </div>
        </div>

        {/* ---- Row 4: Full client table (6-col) ---- */}
        <div className="col-6 glass-card p-6 animate-fade-in-up stagger-1">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-white">
              All Clients ({clients.length})
            </h3>
            <Link
              href="/admin/clients"
              className="text-xs text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
            >
              See all &rarr;
            </Link>
          </div>
          <div className="scrollable-section overflow-x-auto">
            <table className="w-full min-w-[700px]">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.08)]">
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Client</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Workflows</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Messages</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Leads</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Crashes</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]">Last Login</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[#6B7280]"></th>
                </tr>
              </thead>
              <tbody>
                {clients.map((client) => (
                  <tr
                    key={client.id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer"
                    onClick={() => window.location.href = `/admin/clients/${client.id}`}
                  >
                    <td className="px-4 py-3">
                      <p className="text-sm font-medium text-white">{client.full_name}</p>
                      <p className="text-xs text-[#6B7280]">{client.email}</p>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant(client.status)}>{client.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-white tabular-nums">{client.active_workflows}</td>
                    <td className="px-4 py-3 text-sm text-white tabular-nums">
                      {(client.messages_sent + client.messages_received).toLocaleString()}
                    </td>
                    <td className="px-4 py-3 text-sm text-white tabular-nums">{client.leads_created.toLocaleString()}</td>
                    <td className="px-4 py-3">
                      <span className={`text-sm tabular-nums ${client.total_crashes > 0 ? "text-red-400 font-medium" : "text-white"}`}>
                        {client.total_crashes}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-xs text-[#6B7280]">
                      {client.last_login_at
                        ? format(new Date(client.last_login_at), "MMM d, yyyy")
                        : "Never"}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/clients/${client.id}`}
                        className="text-xs text-[#6C63FF] hover:text-[#00D4AA] transition-colors"
                        onClick={(e) => e.stopPropagation()}
                      >
                        View &rarr;
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
