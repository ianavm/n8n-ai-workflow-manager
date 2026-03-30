"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  Calendar,
  CheckSquare,
  Package,
  Heart,
  Plus,
  Upload,
} from "lucide-react";

interface DashboardData {
  upcoming_meetings_count: number;
  pending_tasks_count: number;
  active_products_count: number;
  health_score: number;
  upcoming_meetings: Array<{
    id: string;
    meeting_date: string;
    meeting_type: string;
    status: string;
    teams_meeting_url: string | null;
  }>;
  recent_activity: Array<{
    id: string;
    channel: string;
    direction: string;
    subject: string | null;
    created_at: string;
  }>;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

function StatCard({
  title,
  value,
  icon,
  color,
}: {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div style={glassCard}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
        <span style={{ fontSize: "13px", color: "#6B7280", fontWeight: 500 }}>{title}</span>
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "10px",
            background: `${color}15`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color,
          }}
        >
          {icon}
        </div>
      </div>
      <div style={{ fontSize: "28px", fontWeight: 700, color: "#fff" }}>{value}</div>
    </div>
  );
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr);
  const diffMs = now.getTime() - d.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

const channelColors: Record<string, string> = {
  email: "#00A651",
  whatsapp: "#25D366",
  teams: "#5B5FC7",
  portal: "#00D4AA",
};

export default function AdvisoryDashboard() {
  const supabase = createClient();
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    setLoading(true);
    setError(null);

    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    // Look up fa_clients.id from the portal user
    const { data: client } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("portal_client_id", userData.user.id)
      .single();

    if (!client) {
      setError("No advisory profile linked to your account.");
      setLoading(false);
      return;
    }

    const { data: dashboardData, error: rpcError } = await supabase.rpc(
      "fa_get_client_dashboard",
      { p_client_id: client.id }
    );

    if (rpcError) {
      setError(rpcError.message);
      setLoading(false);
      return;
    }

    setData(dashboardData);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #00A651",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Advisory Dashboard</h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          Your financial advisory overview at a glance.
        </p>
      </div>

      {/* Stat Cards */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(4, 1fr)",
          gap: "20px",
          marginBottom: "28px",
        }}
      >
        <StatCard
          title="Upcoming Meetings"
          value={data.upcoming_meetings_count}
          icon={<Calendar size={18} />}
          color="#00A651"
        />
        <StatCard
          title="Pending Tasks"
          value={data.pending_tasks_count}
          icon={<CheckSquare size={18} />}
          color="#F59E0B"
        />
        <StatCard
          title="Active Products"
          value={data.active_products_count}
          icon={<Package size={18} />}
          color="#00D4AA"
        />
        <StatCard
          title="Health Score"
          value={`${data.health_score}%`}
          icon={<Heart size={18} />}
          color="#FF6D5A"
        />
      </div>

      {/* Two-column layout: Meetings + Activity */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "20px", marginBottom: "28px" }}>
        {/* Upcoming Meetings */}
        <div style={glassCard}>
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "16px" }}>
            Upcoming Meetings
          </h3>
          {data.upcoming_meetings.length === 0 ? (
            <p style={{ fontSize: "13px", color: "#6B7280" }}>No upcoming meetings.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {data.upcoming_meetings.slice(0, 3).map((m) => (
                <div
                  key={m.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "12px",
                    borderRadius: "10px",
                    background: "rgba(255,255,255,0.03)",
                    border: "1px solid rgba(255,255,255,0.04)",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "14px", fontWeight: 500, color: "#fff" }}>
                      {m.meeting_type}
                    </div>
                    <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "2px" }}>
                      {formatDate(m.meeting_date)}
                    </div>
                  </div>
                  {m.teams_meeting_url && (
                    <a
                      href={m.teams_meeting_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        fontSize: "12px",
                        fontWeight: 600,
                        color: "#00A651",
                        textDecoration: "none",
                        padding: "6px 12px",
                        borderRadius: "8px",
                        background: "rgba(108,99,255,0.1)",
                        border: "1px solid rgba(108,99,255,0.2)",
                      }}
                    >
                      Join
                    </a>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Activity */}
        <div style={glassCard}>
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "16px" }}>
            Recent Activity
          </h3>
          {data.recent_activity.length === 0 ? (
            <p style={{ fontSize: "13px", color: "#6B7280" }}>No recent activity.</p>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {data.recent_activity.slice(0, 10).map((a) => (
                <div
                  key={a.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "10px",
                    padding: "8px 0",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                  }}
                >
                  <div
                    style={{
                      width: "8px",
                      height: "8px",
                      borderRadius: "50%",
                      background: channelColors[a.channel] || "#6B7280",
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: "13px", color: "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {a.subject || `${a.channel} ${a.direction}`}
                    </div>
                  </div>
                  <span style={{ fontSize: "11px", color: "#6B7280", flexShrink: 0 }}>
                    {formatRelativeTime(a.created_at)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Quick Actions */}
      <div style={{ display: "flex", gap: "12px" }}>
        <a
          href="/portal/advisory/meetings"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 20px",
            borderRadius: "10px",
            background: "linear-gradient(135deg, #00A651, #5B5FC7)",
            color: "#fff",
            fontSize: "14px",
            fontWeight: 600,
            textDecoration: "none",
            border: "none",
            cursor: "pointer",
          }}
        >
          <Plus size={16} />
          Request Meeting
        </a>
        <a
          href="/portal/advisory/documents"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "8px",
            padding: "12px 20px",
            borderRadius: "10px",
            background: "rgba(255,255,255,0.05)",
            color: "#B0B8C8",
            fontSize: "14px",
            fontWeight: 600,
            textDecoration: "none",
            border: "1px solid rgba(255,255,255,0.08)",
            cursor: "pointer",
          }}
        >
          <Upload size={16} />
          Upload Document
        </a>
      </div>
    </div>
  );
}
