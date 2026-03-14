"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { StatCard } from "@/components/charts/StatCard";
import { TrendChart } from "@/components/charts/TrendChart";
import { Card } from "@/components/ui/Card";
import { DateRangePicker, type DateRange } from "@/components/ui/DateRangePicker";
import { subDays, format } from "date-fns";
import { MessageSquare, UserPlus, AlertTriangle, Activity } from "lucide-react";

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

interface TopClient {
  name: string;
  count: number;
}

export default function AnalyticsPage() {
  const supabase = createClient();
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [customStart, setCustomStart] = useState<string>();
  const [customEnd, setCustomEnd] = useState<string>();
  const [stats, setStats] = useState({ messages: 0, leads: 0, crashes: 0, executions: 0 });
  const [trendData, setTrendData] = useState<Record<string, { date: string; value: number }[]>>({});
  const [topLeadClients, setTopLeadClients] = useState<TopClient[]>([]);
  const [topCrashClients, setTopCrashClients] = useState<TopClient[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const { start, end } = getDateRange(dateRange, customStart, customEnd);

    // Get all events in range
    const { data: events } = await supabase
      .from("stat_events")
      .select("event_type, client_id, created_at")
      .gte("created_at", start)
      .lte("created_at", end);

    const allEvents = events || [];

    // Aggregate stats
    const messages = allEvents.filter(
      (e) => e.event_type === "message_sent" || e.event_type === "message_received"
    ).length;
    const leads = allEvents.filter((e) => e.event_type === "lead_created").length;
    const crashes = allEvents.filter((e) => e.event_type === "workflow_crash").length;

    const { count: executionCount } = await supabase
      .from("workflow_executions")
      .select("*", { count: "exact", head: true })
      .gte("executed_at", start)
      .lte("executed_at", end);

    setStats({ messages, leads, crashes, executions: executionCount || 0 });

    // Daily trends — aggregate across all clients
    const eventTypes = ["message_received", "message_sent", "lead_created", "workflow_crash"];
    const trends: Record<string, { date: string; value: number }[]> = {};

    for (const eventType of eventTypes) {
      const daily: Record<string, number> = {};
      allEvents
        .filter((e) => e.event_type === eventType)
        .forEach((e) => {
          const day = format(new Date(e.created_at), "MMM d");
          daily[day] = (daily[day] || 0) + 1;
        });
      trends[eventType] = Object.entries(daily).map(([date, value]) => ({ date, value }));
    }
    setTrendData(trends);

    // Top clients by leads
    const { data: clients } = await supabase.from("clients").select("id, full_name");
    const clientMap = new Map((clients || []).map((c) => [c.id, c.full_name]));

    const leadsByClient: Record<string, number> = {};
    const crashesByClient: Record<string, number> = {};

    allEvents.forEach((e) => {
      if (e.event_type === "lead_created") {
        leadsByClient[e.client_id] = (leadsByClient[e.client_id] || 0) + 1;
      }
      if (e.event_type === "workflow_crash") {
        crashesByClient[e.client_id] = (crashesByClient[e.client_id] || 0) + 1;
      }
    });

    setTopLeadClients(
      Object.entries(leadsByClient)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([id, count]) => ({ name: clientMap.get(id) || id, count }))
    );

    setTopCrashClients(
      Object.entries(crashesByClient)
        .sort(([, a], [, b]) => b - a)
        .slice(0, 5)
        .map(([id, count]) => ({ name: clientMap.get(id) || id, count }))
    );

    setLoading(false);
  }, [supabase, dateRange, customStart, customEnd]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-8 max-w-7xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="relative">
          <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
          <div className="relative">
            <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
              Global <span className="gradient-text">Analytics</span>
            </h1>
            <p className="text-base text-[#B0B8C8] mt-2">
              Aggregate metrics across all clients
            </p>
          </div>
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

      {/* Aggregate Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="animate-fade-in-up stagger-1">
          <StatCard title="Total Messages" value={stats.messages} icon={<MessageSquare size={20} />} color="purple" loading={loading} />
        </div>
        <div className="animate-fade-in-up stagger-2">
          <StatCard title="Total Leads" value={stats.leads} icon={<UserPlus size={20} />} color="teal" loading={loading} />
        </div>
        <div className="animate-fade-in-up stagger-3">
          <StatCard title="Total Crashes" value={stats.crashes} icon={<AlertTriangle size={20} />} color="red" loading={loading} />
        </div>
        <div className="animate-fade-in-up stagger-4">
          <StatCard title="Workflow Executions" value={stats.executions} icon={<Activity size={20} />} color="coral" loading={loading} />
        </div>
      </div>

      {/* Trend Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <TrendChart data={trendData.message_received || []} title="Messages Received (All Clients)" color="teal" />
        <TrendChart data={trendData.message_sent || []} title="Messages Sent (All Clients)" color="purple" />
        <TrendChart data={trendData.lead_created || []} title="Leads Created (All Clients)" color="teal" />
        <TrendChart data={trendData.workflow_crash || []} title="Crashes (All Clients)" color="purple" />
      </div>

      {/* Top Performers + Flagged */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card>
          <h3 className="text-sm font-medium text-emerald-400 mb-4">Top Clients (Most Leads)</h3>
          <div className="space-y-2">
            {topLeadClients.map((c, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-[rgba(255,255,255,0.02)]">
                <span className="text-sm text-white">{c.name}</span>
                <span className="text-sm text-emerald-400 font-medium">{c.count} leads</span>
              </div>
            ))}
            {topLeadClients.length === 0 && <p className="text-sm text-[#6B7280]">No lead data yet.</p>}
          </div>
        </Card>
        <Card>
          <h3 className="text-sm font-medium text-red-400 mb-4">Most Errors (Needs Attention)</h3>
          <div className="space-y-2">
            {topCrashClients.map((c, i) => (
              <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/10">
                <span className="text-sm text-white">{c.name}</span>
                <span className="text-sm text-red-400 font-medium">{c.count} crashes</span>
              </div>
            ))}
            {topCrashClients.length === 0 && <p className="text-sm text-[#6B7280]">No crashes recorded.</p>}
          </div>
        </Card>
      </div>
    </div>
  );
}
