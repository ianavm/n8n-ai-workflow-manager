"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { TrendChart } from "@/components/charts/TrendChart";
import { UptimeGauge } from "@/components/charts/UptimeGauge";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import { DateRangePicker, type DateRange } from "@/components/ui/DateRangePicker";
import { subDays, format } from "date-fns";
import {
  MessageSquare,
  Send,
  UserPlus,
  AlertTriangle,
  Bot,
  Wifi,
  WifiOff,
  Clock,
  TrendingUp,
  TrendingDown,
} from "lucide-react";
import Link from "next/link";

interface ClientDetail {
  id: string;
  full_name: string;
  email: string;
  company_name: string | null;
  status: string;
  api_key: string;
  created_at: string;
  last_login_at: string | null;
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

export default function ClientDetailPage() {
  const params = useParams();
  const clientId = params.id as string;
  const supabase = createClient();

  const [client, setClient] = useState<ClientDetail | null>(null);
  const [stats, setStats] = useState({ message_received: 0, message_sent: 0, lead_created: 0, workflow_crash: 0 });
  const [trendData, setTrendData] = useState<Record<string, { date: string; value: number }[]>>({});
  const [workflows, setWorkflows] = useState<{ id: string; name: string; status: string; platform: string }[]>([]);
  const [uptime, setUptime] = useState({ total_executions: 0, successful: 0, failed: 0, success_rate: 100 });
  const [notes, setNotes] = useState<{ id: string; content: string; created_at: string }[]>([]);
  const [newNote, setNewNote] = useState("");
  const [noteModal, setNoteModal] = useState(false);
  const [agentProfiles, setAgentProfiles] = useState<{
    id: string;
    agent_id: string;
    agent_name: string;
    phone_number: string | null;
    is_online: boolean;
    manual_override: string | null;
    manual_override_expiry: string | null;
    business_hours_start: string;
    business_hours_end: string;
    updated_at: string;
  }[]>([]);
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [customStart, setCustomStart] = useState<string>();
  const [customEnd, setCustomEnd] = useState<string>();
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    const { start, end } = getDateRange(dateRange, customStart, customEnd);

    const { data: clientData } = await supabase
      .from("clients")
      .select("*")
      .eq("id", clientId)
      .single();
    if (clientData) setClient(clientData);

    const { data: events } = await supabase
      .from("stat_events")
      .select("event_type")
      .eq("client_id", clientId)
      .gte("created_at", start)
      .lte("created_at", end);

    const counts = { message_received: 0, message_sent: 0, lead_created: 0, workflow_crash: 0 };
    (events || []).forEach((e) => {
      if (e.event_type in counts) counts[e.event_type as keyof typeof counts]++;
    });
    setStats(counts);

    const trends: Record<string, { date: string; value: number }[]> = {};
    for (const eventType of ["message_received", "message_sent", "lead_created", "workflow_crash"]) {
      const { data: dailyData } = await supabase.rpc("get_daily_stats", {
        p_client_id: clientId,
        p_event_type: eventType,
        p_start_date: start,
        p_end_date: end,
      });
      trends[eventType] = (dailyData || []).map((d: { day: string; count: number }) => ({
        date: format(new Date(d.day), "MMM d"),
        value: d.count,
      }));
    }
    setTrendData(trends);

    const { data: wfs } = await supabase
      .from("workflows")
      .select("id, name, status, platform")
      .eq("client_id", clientId);
    setWorkflows(wfs || []);

    const { data: uptimeData } = await supabase.rpc("get_uptime_stats", {
      p_client_id: clientId,
      p_start_date: start,
      p_end_date: end,
    });
    if (uptimeData?.[0]) setUptime(uptimeData[0]);

    const { data: notesData } = await supabase
      .from("client_notes")
      .select("id, content, created_at")
      .eq("client_id", clientId)
      .order("created_at", { ascending: false });
    setNotes(notesData || []);

    const { data: agentsData } = await supabase
      .from("agent_profiles")
      .select("id, agent_id, agent_name, phone_number, is_online, manual_override, manual_override_expiry, business_hours_start, business_hours_end, updated_at")
      .eq("client_id", clientId)
      .order("agent_name");
    setAgentProfiles(agentsData || []);

    setLoading(false);
  }, [supabase, clientId, dateRange, customStart, customEnd]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  async function addNote() {
    if (!newNote.trim()) return;
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;

    const { data: admin } = await supabase
      .from("admin_users")
      .select("id")
      .eq("auth_user_id", user.id)
      .single();

    if (!admin) return;

    await supabase.from("client_notes").insert({
      client_id: clientId,
      admin_id: admin.id,
      content: newNote.trim(),
    });

    setNewNote("");
    setNoteModal(false);
    fetchData();
  }

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "suspended" ? "danger" : "warning";

  const wfStatusColor = (s: string) =>
    s === "active" ? "#10B981" : s === "paused" ? "#F59E0B" : "#EF4444";

  if (loading && !client) {
    return (
      <div className="space-y-6 max-w-[1200px]">
        <Skeleton className="h-48 w-full rounded-2xl" />
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-32 rounded-2xl" />
          ))}
        </div>
      </div>
    );
  }

  const initials = client?.full_name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .slice(0, 2)
    .toUpperCase() || "??";

  return (
    <div className="max-w-[1200px]">
      {/* Bento Grid */}
      <div className="bento-grid">

        {/* ---- Hero Profile (full width, gradient border) ---- */}
        <div className="col-6 animate-fade-in-up stagger-1">
          <div className="grad-border">
            <div className="grad-border-inner relative">
              <div className="welcome-blob b1" />
              <div className="welcome-blob b2" />
              <div className="relative z-10">
                <Link
                  href="/admin/clients"
                  className="text-xs text-[#6C63FF] hover:text-[#00D4AA] mb-3 inline-block transition-colors"
                >
                  &larr; All Clients
                </Link>
                <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
                  {/* Avatar */}
                  <div
                    className="w-16 h-16 rounded-2xl flex items-center justify-center text-xl font-bold text-white flex-shrink-0"
                    style={{ background: "linear-gradient(135deg, #6C63FF, #00D4AA)" }}
                  >
                    {initials}
                  </div>
                  {/* Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                      <h1 className="text-2xl font-bold text-white">{client?.full_name}</h1>
                      <Badge variant={statusVariant(client?.status || "active")}>
                        {client?.status}
                      </Badge>
                    </div>
                    <div className="text-sm text-[var(--text-muted)] mt-1">
                      {client?.email}
                      {client?.company_name && (
                        <span className="text-[var(--text-dim)]"> | {client.company_name}</span>
                      )}
                    </div>
                    <div className="text-xs text-[var(--text-dim)] mt-1">
                      Member since {client?.created_at ? format(new Date(client.created_at), "MMM yyyy") : "—"}
                    </div>
                  </div>
                  {/* Date range + API key */}
                  <div className="flex flex-col gap-2 items-end flex-shrink-0">
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
                    <div className="text-[11px] text-[var(--text-dim)]">
                      API Key: <code className="text-[var(--text-muted)] bg-[rgba(255,255,255,0.05)] px-1 py-0.5 rounded text-[10px]">{client?.api_key}</code>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* ---- Stats Row: 2+2+1+1 ---- */}
        <div className="col-2 floating-card p-6 animate-fade-in-up stagger-1">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{ background: "rgba(0,212,170,0.1)", color: "#00D4AA" }}>
            <MessageSquare size={20} />
          </div>
          <div className="stat-number-shimmer mb-1.5">{stats.message_received.toLocaleString()}</div>
          <div className="text-sm text-[var(--text-muted)]">Messages Received</div>
          {stats.message_received > 0 && (
            <span className="inline-flex items-center gap-1 mt-2.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[rgba(16,185,129,0.12)] text-[#10B981]">
              <TrendingUp size={12} /> +12%
            </span>
          )}
        </div>

        <div className="col-2 floating-card p-6 animate-fade-in-up stagger-2">
          <div className="w-12 h-12 rounded-xl flex items-center justify-center mb-4" style={{ background: "rgba(108,99,255,0.1)", color: "#6C63FF" }}>
            <Send size={20} />
          </div>
          <div className="stat-number-shimmer mb-1.5">{stats.message_sent.toLocaleString()}</div>
          <div className="text-sm text-[var(--text-muted)]">Messages Sent</div>
          {stats.message_sent > 0 && (
            <span className="inline-flex items-center gap-1 mt-2.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-[rgba(16,185,129,0.12)] text-[#10B981]">
              <TrendingUp size={12} /> +8%
            </span>
          )}
        </div>

        <div className="col-1 floating-card p-5 animate-fade-in-up stagger-3">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: "rgba(0,212,170,0.1)", color: "#00D4AA" }}>
            <UserPlus size={16} />
          </div>
          <div className="stat-number-shimmer mb-1" style={{ fontSize: 24 }}>{stats.lead_created.toLocaleString()}</div>
          <div className="text-[11px] text-[var(--text-muted)]">Leads</div>
          {stats.lead_created > 0 && (
            <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[rgba(16,185,129,0.12)] text-[#10B981]">
              +24%
            </span>
          )}
        </div>

        <div className="col-1 floating-card p-5 animate-fade-in-up stagger-4">
          <div className="w-9 h-9 rounded-lg flex items-center justify-center mb-3" style={{ background: "rgba(239,68,68,0.1)", color: "#EF4444" }}>
            <AlertTriangle size={16} />
          </div>
          <div className="stat-number-shimmer mb-1" style={{ fontSize: 24 }}>{stats.workflow_crash}</div>
          <div className="text-[11px] text-[var(--text-muted)]">Crashes</div>
          {stats.workflow_crash > 0 && (
            <span className="inline-flex items-center gap-1 mt-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[rgba(239,68,68,0.12)] text-[#EF4444]">
              <TrendingDown size={10} /> {stats.workflow_crash}
            </span>
          )}
        </div>

        {/* ---- Charts: Messages Received (3-col, 2-row) + Messages Sent (3-col) + Uptime (3-col) ---- */}
        <div className="col-3 row-2 animate-fade-in-up stagger-1">
          <TrendChart
            data={trendData.message_received || []}
            title="Messages Received"
            color="teal"
            height={240}
          />
        </div>

        <div className="col-3 animate-fade-in-up stagger-2">
          <TrendChart
            data={trendData.message_sent || []}
            title="Messages Sent"
            color="purple"
          />
        </div>

        <div className="col-3 animate-fade-in-up stagger-3">
          <UptimeGauge
            successRate={uptime.success_rate}
            totalExecutions={uptime.total_executions}
            successful={uptime.successful}
            failed={uptime.failed}
          />
        </div>

        {/* ---- Bottom Row: Leads Chart + Workflows + Agents ---- */}
        <div className="col-2 animate-fade-in-up stagger-1">
          <TrendChart
            data={trendData.lead_created || []}
            title="Leads Created"
            color="teal"
            height={120}
          />
        </div>

        {/* Workflows */}
        <div className="col-2 glass-card p-6 animate-fade-in-up stagger-2">
          <div className="text-sm font-semibold text-white mb-4">
            Workflows ({workflows.length})
          </div>
          <div className="scrollable-section-sm space-y-2">
            {workflows.length === 0 ? (
              <p className="text-sm text-[var(--text-dim)]">No workflows assigned.</p>
            ) : (
              workflows.map((wf) => (
                <div
                  key={wf.id}
                  className="wf-item cursor-pointer hover:bg-[rgba(255,255,255,0.06)] transition-colors"
                >
                  <div
                    className="wf-dot"
                    style={{ background: wfStatusColor(wf.status) }}
                  />
                  <span className="wf-name flex-1">{wf.name}</span>
                  <span
                    className="wf-status text-[11px] font-semibold"
                    style={{ color: wfStatusColor(wf.status) }}
                  >
                    {wf.status}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Agents */}
        <div className="col-2 glass-card p-6 animate-fade-in-up stagger-3">
          <div className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
            <Bot size={14} className="text-[#6C63FF]" />
            AI Agents ({agentProfiles.length})
          </div>
          <div className="scrollable-section-sm space-y-2">
            {agentProfiles.length === 0 ? (
              <p className="text-sm text-[var(--text-dim)]">No agents assigned.</p>
            ) : (
              agentProfiles.map((agent) => {
                const hasOverride = agent.manual_override && (!agent.manual_override_expiry || new Date(agent.manual_override_expiry).getTime() > Date.now());
                return (
                  <div
                    key={agent.id}
                    className="p-3 rounded-xl bg-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.06)] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${agent.is_online ? "bg-[#10B981] pulse-dot" : "bg-[#6B7280]"}`}
                      />
                      <span className="text-[13px] font-semibold text-white">{agent.agent_name}</span>
                      <span className="ml-auto">
                        <Badge variant={agent.is_online ? "success" : "danger"} pulse={agent.is_online}>
                          {agent.is_online ? (
                            <><Wifi size={10} /> Online</>
                          ) : (
                            <><WifiOff size={10} /> Offline</>
                          )}
                        </Badge>
                      </span>
                    </div>
                    <div className="text-[11px] text-[var(--text-dim)] flex items-center gap-2">
                      <span>{agent.business_hours_start} - {agent.business_hours_end}</span>
                      {hasOverride ? (
                        <Badge variant="warning">{agent.manual_override}</Badge>
                      ) : (
                        <span className="flex items-center gap-1"><Clock size={10} /> Auto</span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* ---- Notes (full width, gradient border, timeline) ---- */}
        <div className="col-6 animate-fade-in-up stagger-1">
          <div className="grad-border">
            <div className="grad-border-inner">
              <div className="flex items-center justify-between mb-5">
                <div className="text-sm font-semibold text-white">Internal Notes</div>
                <Button size="sm" variant="secondary" onClick={() => setNoteModal(true)}>
                  + Add Note
                </Button>
              </div>
              <div className="scrollable-section">
                {notes.length === 0 ? (
                  <p className="text-sm text-[var(--text-dim)]">No notes yet.</p>
                ) : (
                  <div className="notes-timeline">
                    {notes.map((note) => (
                      <div key={note.id} className="timeline-item">
                        <div className="timeline-note">
                          <div className="text-xs text-[var(--text-dim)] mb-1.5">
                            {format(new Date(note.created_at), "MMM d, yyyy 'at' h:mm a")}
                          </div>
                          <div className="text-[13px] text-[var(--text-muted)] leading-relaxed">
                            {note.content}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Add Note Modal */}
      <Modal open={noteModal} onClose={() => setNoteModal(false)} title="Add Internal Note">
        <textarea
          value={newNote}
          onChange={(e) => setNewNote(e.target.value)}
          placeholder="Write a note about this client..."
          rows={4}
          className="w-full mb-4"
        />
        <div className="flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setNoteModal(false)}>Cancel</Button>
          <Button onClick={addNote}>Save Note</Button>
        </div>
      </Modal>
    </div>
  );
}
