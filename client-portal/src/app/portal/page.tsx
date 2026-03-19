"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { StatCard } from "@/components/charts/StatCard";
import { TrendChart } from "@/components/charts/TrendChart";
import { UptimeGauge } from "@/components/charts/UptimeGauge";
import { DateRangePicker, type DateRange } from "@/components/ui/DateRangePicker";
import { Badge } from "@/components/ui/Badge";
import { subDays, format } from "date-fns";
import { MessageSquare, Send, UserPlus, AlertTriangle, Search, FileBarChart, Settings } from "lucide-react";

interface ClientProfile {
  id: string;
  full_name: string;
  company_name: string;
}

interface StatSummary {
  message_received: number;
  message_sent: number;
  lead_created: number;
  workflow_crash: number;
}

interface TrendData {
  date: string;
  value: number;
}

interface Workflow {
  id: string;
  name: string;
  status: string;
  platform: string;
  updated_at: string;
}

interface CrashEvent {
  id: number;
  created_at: string;
  metadata: Record<string, unknown>;
  workflow_id: string;
}

interface UptimeData {
  total_executions: number;
  successful: number;
  failed: number;
  success_rate: number;
}

function getDateRange(range: DateRange, customStart?: string, customEnd?: string) {
  const end = new Date();
  let start: Date;
  if (range === "7d") start = subDays(end, 7);
  else if (range === "30d") start = subDays(end, 30);
  else if (range === "90d") start = subDays(end, 90);
  else {
    start = customStart ? new Date(customStart) : subDays(end, 30);
    if (customEnd) end.setTime(new Date(customEnd).getTime());
  }
  return { start: start.toISOString(), end: end.toISOString() };
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default function PortalDashboard() {
  const supabase = createClient();
  const [profile, setProfile] = useState<ClientProfile | null>(null);
  const [stats, setStats] = useState<StatSummary>({
    message_received: 0,
    message_sent: 0,
    lead_created: 0,
    workflow_crash: 0,
  });
  const [trendData, setTrendData] = useState<Record<string, TrendData[]>>({});
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [crashes, setCrashes] = useState<CrashEvent[]>([]);
  const [uptime, setUptime] = useState<UptimeData>({
    total_executions: 0,
    successful: 0,
    failed: 0,
    success_rate: 100,
  });
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [customStart, setCustomStart] = useState<string>();
  const [customEnd, setCustomEnd] = useState<string>();
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const { start, end } = getDateRange(dateRange, customStart, customEnd);

    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return;

    const { data: clientProfile } = await supabase
      .from("clients")
      .select("id, full_name, company_name")
      .eq("auth_user_id", user.id)
      .single();

    if (!clientProfile) return;
    setProfile(clientProfile);

    const clientId = clientProfile.id;

    const { data: events } = await supabase
      .from("stat_events")
      .select("event_type")
      .eq("client_id", clientId)
      .gte("created_at", start)
      .lte("created_at", end);

    const counts: StatSummary = {
      message_received: 0,
      message_sent: 0,
      lead_created: 0,
      workflow_crash: 0,
    };
    (events || []).forEach((e) => {
      if (e.event_type in counts) {
        counts[e.event_type as keyof StatSummary]++;
      }
    });
    setStats(counts);

    const trends: Record<string, TrendData[]> = {};
    for (const eventType of [
      "message_received",
      "message_sent",
      "lead_created",
      "workflow_crash",
    ]) {
      const { data: dailyData } = await supabase.rpc("get_daily_stats", {
        p_client_id: clientId,
        p_event_type: eventType,
        p_start_date: start,
        p_end_date: end,
      });
      trends[eventType] = (dailyData || []).map(
        (d: { day: string; count: number }) => ({
          date: format(new Date(d.day), "MMM d"),
          value: d.count,
        })
      );
    }
    setTrendData(trends);

    const { data: wfs } = await supabase
      .from("workflows")
      .select("*")
      .eq("client_id", clientId)
      .order("updated_at", { ascending: false });
    setWorkflows(wfs || []);

    const { data: crashEvents } = await supabase
      .from("stat_events")
      .select("id, created_at, metadata, workflow_id")
      .eq("client_id", clientId)
      .eq("event_type", "workflow_crash")
      .order("created_at", { ascending: false })
      .limit(10);
    setCrashes(crashEvents || []);

    const { data: uptimeData } = await supabase.rpc("get_uptime_stats", {
      p_client_id: clientId,
      p_start_date: start,
      p_end_date: end,
    });
    if (uptimeData?.[0]) {
      setUptime(uptimeData[0]);
    }

    setLoading(false);
  }, [supabase, dateRange, customStart, customEnd]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading && !profile) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "60vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #6C63FF",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "paused" ? "warning" : "danger";

  const firstName = profile?.full_name?.split(" ")[0] || "there";
  const now = new Date();

  const statusDotColor = (s: string) =>
    s === "active" ? "#10B981" : s === "paused" ? "#F59E0B" : "#EF4444";

  const statusLabel = (s: string) =>
    s === "active" ? "Running" : s === "paused" ? "Paused" : "Error";

  const statusLabelColor = (s: string) =>
    s === "active" ? "#10B981" : s === "paused" ? "#F59E0B" : "#EF4444";

  return (
    <div>
      {/* ── Top Bar (V1 preview) ── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: "32px",
          animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        }}
      >
        <div>
          <div style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>
            {getGreeting()}, {firstName}
          </div>
          <div style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
            Here&apos;s what&apos;s happening with your AI workforce today.
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div style={{ fontSize: "13px", color: "#6B7280", textAlign: "right" }}>
            {format(now, "EEEE, d MMMM yyyy")}
            <br />
            <span style={{ color: "#6B7280", fontSize: "12px" }}>
              {format(now, "HH:mm")} SAST
            </span>
          </div>
          <DateRangePicker
            value={dateRange}
            onChange={(range, start, end) => {
              setDateRange(range);
              setCustomStart(start);
              setCustomEnd(end);
            }}
            customStart={customStart}
            customEnd={customEnd}
          />
        </div>
      </div>

      {/* ── Stat Cards Grid (4 columns, 24px gap) ── */}
      <div
        className="stat-grid-portal"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "28px",
          marginBottom: "32px",
        }}
      >
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.1s both" }}>
          <StatCard title="Messages Sent" value={stats.message_sent} icon={<Send size={22} />} color="purple" loading={loading} />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.2s both" }}>
          <StatCard title="Leads Generated" value={stats.lead_created} icon={<UserPlus size={22} />} color="teal" loading={loading} />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.3s both" }}>
          <StatCard title="Active Workflows" value={workflows.length} icon={<MessageSquare size={22} />} color="purple" loading={loading} />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.4s both" }}>
          <StatCard title="Success Rate" value={`${uptime.success_rate}%`} icon={<AlertTriangle size={22} />} color="teal" loading={loading} />
        </div>
      </div>

      {/* ── Gradient Divider ── */}
      <div className="gradient-divider" style={{ marginBottom: "32px" }} />

      {/* ── Welcome Banner (V1 preview gradient border technique) ── */}
      <div
        className="welcome-banner"
        style={{
          marginBottom: "32px",
          animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.5s both",
        }}
      >
        <div className="welcome-blob b1" />
        <div className="welcome-blob b2" />
        <div style={{ position: "relative", zIndex: 1 }}>
          <h2 style={{ fontSize: "24px", fontWeight: 600, color: "#fff", marginBottom: "6px" }}>
            Your AI workforce is running smoothly
          </h2>
          <p style={{ fontSize: "14px", color: "#B0B8C8", marginBottom: "24px" }}>
            {workflows.length} workflows processed {stats.message_sent.toLocaleString()} messages today with a {uptime.success_rate}% success rate.{" "}
            {stats.lead_created > 0
              ? `${stats.lead_created} new leads are awaiting review.`
              : "No new leads today."}
          </p>
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            <a href="/portal/workflows" className="btn-gradient">
              <Search size={16} />
              Review Leads
            </a>
            <a href="/portal/reports" className="btn-outline">
              <FileBarChart size={16} />
              View Reports
            </a>
            <a href="/portal/settings" className="btn-outline">
              <Settings size={16} />
              Settings
            </a>
          </div>
        </div>
      </div>

      {/* ── Chart Grid (2x2, 24px gap) ── */}
      <div
        className="chart-grid-portal"
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gap: "28px",
          marginBottom: "32px",
        }}
      >
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.6s both" }}>
          <TrendChart
            data={trendData.message_received || []}
            title="Messages Over Time"
            subtitle="Last 7 days"
            color="purple"
          />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.7s both" }}>
          <TrendChart
            data={trendData.lead_created || []}
            title="Lead Conversion"
            subtitle="Conversion funnel"
            color="teal"
          />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.8s both" }}>
          <TrendChart
            data={trendData.message_sent || []}
            title="Workflow Runs"
            subtitle="Executions per day"
            color="purple"
          />
        </div>
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.9s both" }}>
          <TrendChart
            data={trendData.workflow_crash || []}
            title="Error Rate"
            subtitle="Failures per 1,000 runs"
            color="teal"
          />
        </div>
      </div>

      {/* ── Bottom Row (3 columns: Uptime, Active Workflows, Recent Errors) ── */}
      <div
        className="bottom-grid-portal"
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr 1fr",
          gap: "28px",
        }}
      >
        {/* Uptime Gauge */}
        <div style={{ animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 1.0s both" }}>
          <UptimeGauge
            successRate={uptime.success_rate}
            totalExecutions={uptime.total_executions}
            successful={uptime.successful}
            failed={uptime.failed}
          />
        </div>

        {/* Active Workflows */}
        <div
          className="glass-card"
          style={{
            padding: "28px",
            animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 1.1s both",
          }}
        >
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "20px" }}>
            Active Workflows
          </h3>
          <div className="wf-list">
            {workflows.length === 0 ? (
              <p style={{ fontSize: "13px", color: "#6B7280" }}>No workflows configured yet.</p>
            ) : (
              workflows.slice(0, 5).map((wf) => (
                <div key={wf.id} className="wf-item">
                  <span
                    className="wf-dot"
                    style={{ background: statusDotColor(wf.status) }}
                  />
                  <span className="wf-name">{wf.name}</span>
                  <span
                    className="wf-status"
                    style={{ color: statusLabelColor(wf.status) }}
                  >
                    {statusLabel(wf.status)}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Recent Errors */}
        <div
          className="glass-card"
          style={{
            padding: "28px",
            animation: "fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) 1.2s both",
          }}
        >
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "20px" }}>
            Recent Errors
          </h3>
          <div className="err-list">
            {crashes.length === 0 ? (
              <p style={{ fontSize: "13px", color: "#6B7280" }}>No recent errors.</p>
            ) : (
              crashes.slice(0, 3).map((crash) => (
                <div key={crash.id} className="err-item">
                  <span className="err-badge">
                    {(crash.metadata as Record<string, string>)?.code || "ERR"}
                  </span>
                  <span className="err-text">
                    {(crash.metadata as Record<string, string>)?.error || "Unknown error"}
                  </span>
                  <span className="err-time">
                    {format(new Date(crash.created_at), "h'h' ago")}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
