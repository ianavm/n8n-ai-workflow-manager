"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import {
  Users,
  Calendar,
  CheckSquare,
  AlertTriangle,
  Clock,
  Video,
  ExternalLink,
  TrendingUp,
} from "lucide-react";

interface PipelineSummary {
  [stage: string]: number;
}

interface MeetingClient {
  id: string;
  first_name: string;
  last_name: string;
}

interface UpcomingMeeting {
  id: string;
  title: string;
  scheduled_at: string;
  status: string;
  meeting_type: string;
  location: string | null;
  teams_meeting_url: string | null;
  fa_clients: MeetingClient;
}

interface RecentMeeting {
  id: string;
  title: string;
  scheduled_at: string;
  ended_at: string | null;
  status: string;
  meeting_type: string;
  fa_clients: MeetingClient;
}

interface TaskClient {
  id: string;
  first_name: string;
  last_name: string;
}

interface OverdueTask {
  id: string;
  title: string;
  due_date: string;
  priority: string;
  status: string;
  fa_clients: TaskClient;
}

interface DashboardData {
  my_clients: number;
  upcoming_meetings: number;
  pending_tasks: number;
  overdue_tasks: number;
  meetings_this_week: number;
  meetings_completed_this_month: number;
  pipeline_summary: PipelineSummary | null;
  recent_meetings: RecentMeeting[];
  upcoming_meetings_list: UpcomingMeeting[];
  overdue_tasks_list: OverdueTask[];
}

const PIPELINE_ORDER = [
  "lead",
  "prospect",
  "discovery",
  "proposal",
  "onboarding",
  "active",
  "review",
  "churned",
];

const stageColor = (stage: string): string => {
  switch (stage) {
    case "lead":
      return "#00A651";
    case "prospect":
      return "#8B5CF6";
    case "discovery":
      return "#F59E0B";
    case "proposal":
      return "#F97316";
    case "onboarding":
      return "#3B82F6";
    case "active":
      return "#10B981";
    case "review":
      return "#6B7280";
    case "churned":
      return "#EF4444";
    default:
      return "#6B7280";
  }
};

const meetingStatusBadge = (
  status: string
): "default" | "success" | "warning" | "danger" | "purple" | "coral" => {
  switch (status) {
    case "completed":
      return "success";
    case "scheduled":
    case "confirmed":
      return "purple";
    case "cancelled":
      return "danger";
    case "no_show":
      return "warning";
    default:
      return "default";
  }
};

const priorityBadge = (
  priority: string
): "default" | "success" | "warning" | "danger" | "purple" | "coral" => {
  switch (priority) {
    case "urgent":
      return "danger";
    case "high":
      return "coral";
    case "medium":
      return "warning";
    case "low":
      return "default";
    default:
      return "default";
  }
};

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString("en-ZA", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
  });
}

function formatRelativeDate(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor(
    (now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24)
  );

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays}d ago`;
  return formatDate(dateStr);
}

function daysOverdue(dateStr: string): number {
  const date = new Date(dateStr);
  const now = new Date();
  return Math.floor((now.getTime() - date.getTime()) / (1000 * 60 * 60 * 24));
}

export default function MyDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetch("/api/advisory/adviser-dashboard");
    if (res.ok) {
      const json = await res.json();
      setData(json.data);
    } else if (res.status === 403) {
      setError("Access denied. Adviser role required.");
    } else {
      setError("Failed to load dashboard.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#00A651] border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="glass-card p-12 text-center">
        <AlertTriangle
          size={32}
          className="text-[#EF4444] mx-auto mb-3 opacity-70"
        />
        <p className="text-sm text-[#EF4444]">
          {error ?? "Failed to load dashboard data."}
        </p>
      </div>
    );
  }

  const pipelineStages = PIPELINE_ORDER.filter(
    (s) => data.pipeline_summary?.[s]
  );
  const totalPipelineClients = pipelineStages.reduce(
    (sum, s) => sum + (data.pipeline_summary?.[s] ?? 0),
    0
  );

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            My <span className="gradient-text">Dashboard</span>
          </h1>
          <p className="text-sm text-[#B0B8C8] mt-2">
            {data.meetings_completed_this_month} meetings completed this month
          </p>
        </div>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<Users size={20} />}
          label="My Clients"
          value={data.my_clients}
          color="#00A651"
        />
        <StatCard
          icon={<Calendar size={20} />}
          label="Upcoming Meetings"
          value={data.upcoming_meetings}
          color="#00D4AA"
        />
        <StatCard
          icon={<CheckSquare size={20} />}
          label="Pending Tasks"
          value={data.pending_tasks}
          color="#F59E0B"
        />
        <StatCard
          icon={<AlertTriangle size={20} />}
          label="Overdue Tasks"
          value={data.overdue_tasks}
          color={data.overdue_tasks > 0 ? "#EF4444" : "#10B981"}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* This Week's Meetings */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Calendar size={16} className="text-[#00D4AA]" />
            <h2 className="text-sm font-semibold text-white">
              Upcoming Meetings
            </h2>
            <span className="text-xs text-[#6B7280] ml-auto">
              {data.meetings_this_week} this week
            </span>
          </div>

          {data.upcoming_meetings_list.length === 0 ? (
            <p className="text-xs text-[#6B7280] text-center py-6">
              No upcoming meetings scheduled.
            </p>
          ) : (
            <div className="space-y-3">
              {data.upcoming_meetings_list.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center gap-3 p-3 bg-[rgba(255,255,255,0.03)] rounded-lg"
                >
                  <div className="flex-shrink-0 w-12 text-center">
                    <p className="text-xs text-[#6B7280]">
                      {formatDate(m.scheduled_at)}
                    </p>
                    <p className="text-sm font-bold text-white">
                      {formatTime(m.scheduled_at)}
                    </p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">
                      {m.fa_clients.first_name} {m.fa_clients.last_name}
                    </p>
                    <p className="text-xs text-[#6B7280] truncate">
                      {m.title} - {m.meeting_type}
                    </p>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    {m.teams_meeting_url && (
                      <a
                        href={m.teams_meeting_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-[#00A651] hover:text-[#5A52E0] transition-colors"
                        title="Join Teams meeting"
                      >
                        <Video size={14} />
                      </a>
                    )}
                    <Badge variant={meetingStatusBadge(m.status)}>
                      {m.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* My Pipeline */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp size={16} className="text-[#00A651]" />
            <h2 className="text-sm font-semibold text-white">My Pipeline</h2>
            <span className="text-xs text-[#6B7280] ml-auto">
              {totalPipelineClients} clients
            </span>
          </div>

          {pipelineStages.length === 0 ? (
            <p className="text-xs text-[#6B7280] text-center py-6">
              No clients in pipeline yet.
            </p>
          ) : (
            <div className="space-y-3">
              {PIPELINE_ORDER.map((stage) => {
                const count = data.pipeline_summary?.[stage] ?? 0;
                if (count === 0) return null;
                const pct =
                  totalPipelineClients > 0
                    ? (count / totalPipelineClients) * 100
                    : 0;

                return (
                  <div key={stage} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#B0B8C8] capitalize">
                        {stage}
                      </span>
                      <span className="text-xs font-medium text-white">
                        {count}
                      </span>
                    </div>
                    <div className="h-2 bg-[rgba(255,255,255,0.06)] rounded-full overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${pct}%`,
                          backgroundColor: stageColor(stage),
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Overdue Tasks */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle size={16} className="text-[#EF4444]" />
            <h2 className="text-sm font-semibold text-white">Overdue Tasks</h2>
          </div>

          {data.overdue_tasks_list.length === 0 ? (
            <div className="text-center py-6">
              <CheckSquare
                size={24}
                className="text-[#10B981] mx-auto mb-2 opacity-70"
              />
              <p className="text-xs text-[#10B981]">
                All caught up! No overdue tasks.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {data.overdue_tasks_list.map((t) => (
                <div
                  key={t.id}
                  className="flex items-center gap-3 p-3 bg-[rgba(255,255,255,0.03)] rounded-lg"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">{t.title}</p>
                    <p className="text-xs text-[#6B7280]">
                      {t.fa_clients.first_name} {t.fa_clients.last_name} -{" "}
                      <span className="text-[#EF4444]">
                        {daysOverdue(t.due_date)}d overdue
                      </span>
                    </p>
                  </div>
                  <Badge variant={priorityBadge(t.priority)}>
                    {t.priority}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div className="glass-card p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock size={16} className="text-[#B0B8C8]" />
            <h2 className="text-sm font-semibold text-white">
              Recent Activity
            </h2>
          </div>

          {data.recent_meetings.length === 0 ? (
            <p className="text-xs text-[#6B7280] text-center py-6">
              No recent meeting activity.
            </p>
          ) : (
            <div className="space-y-3">
              {data.recent_meetings.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center gap-3 p-3 bg-[rgba(255,255,255,0.03)] rounded-lg"
                >
                  <div className="flex-shrink-0 text-xs text-[#6B7280] w-16">
                    {formatRelativeDate(m.scheduled_at)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm text-white truncate">
                      {m.fa_clients.first_name} {m.fa_clients.last_name}
                    </p>
                    <p className="text-xs text-[#6B7280] truncate">
                      {m.title} - {m.meeting_type}
                    </p>
                  </div>
                  <Badge variant={meetingStatusBadge(m.status)}>
                    {m.status}
                  </Badge>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: number;
  color: string;
}

function StatCard({ icon, label, value, color }: StatCardProps) {
  return (
    <div className="glass-card p-4">
      <div className="flex items-center gap-2 mb-2">
        <div style={{ color }}>{icon}</div>
        <span className="text-xs text-[#6B7280] uppercase tracking-wider">
          {label}
        </span>
      </div>
      <p className="text-2xl font-bold text-white">{value}</p>
    </div>
  );
}
