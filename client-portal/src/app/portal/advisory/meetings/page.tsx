"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import { Calendar, Video, Clock, Filter } from "lucide-react";

interface FaMeeting {
  id: string;
  meeting_date: string;
  meeting_type: string;
  status: string;
  adviser_name: string | null;
  teams_meeting_url: string | null;
  duration_minutes: number | null;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

type MeetingFilter = "all" | "upcoming" | "completed";

function statusBadge(status: string) {
  const map: Record<string, { color: string; bg: string }> = {
    scheduled: { color: "#00A651", bg: "rgba(108,99,255,0.1)" },
    confirmed: { color: "#00D4AA", bg: "rgba(0,212,170,0.1)" },
    completed: { color: "#10B981", bg: "rgba(16,185,129,0.1)" },
    cancelled: { color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
    no_show: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
  };
  const s = map[status.toLowerCase()] || { color: "#6B7280", bg: "rgba(107,114,128,0.1)" };
  return s;
}

function formatMeetingDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-ZA", {
    weekday: "short",
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function isUpcoming(dateStr: string, status: string): boolean {
  return new Date(dateStr) > new Date() && status !== "completed" && status !== "cancelled";
}

export default function AdvisoryMeetings() {
  const supabase = createClient();
  const [meetings, setMeetings] = useState<FaMeeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<MeetingFilter>("all");

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("portal_client_id", userData.user.id)
      .single();

    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: meetingData, error: meetingErr } = await supabase
      .from("fa_meetings")
      .select("id, meeting_date, meeting_type, status, adviser_name, teams_meeting_url, duration_minutes")
      .eq("client_id", client.id)
      .order("meeting_date", { ascending: false });

    if (meetingErr) {
      setError(meetingErr.message);
      setLoading(false);
      return;
    }

    setMeetings(meetingData || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  const filtered = meetings.filter((m) => {
    if (filter === "upcoming") return isUpcoming(m.meeting_date, m.status);
    if (filter === "completed") return m.status === "completed";
    return true;
  });

  const filterBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: 500,
    border: "1px solid",
    borderColor: active ? "rgba(108,99,255,0.3)" : "rgba(255,255,255,0.08)",
    background: active ? "rgba(108,99,255,0.15)" : "transparent",
    color: active ? "#fff" : "#6B7280",
    cursor: "pointer",
    fontFamily: "inherit",
  });

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

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Meetings</h1>
          <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
            Your advisory meetings and consultations.
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Filter size={14} style={{ color: "#6B7280" }} />
          <button style={filterBtnStyle(filter === "all")} onClick={() => setFilter("all")}>All</button>
          <button style={filterBtnStyle(filter === "upcoming")} onClick={() => setFilter("upcoming")}>Upcoming</button>
          <button style={filterBtnStyle(filter === "completed")} onClick={() => setFilter("completed")}>Completed</button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <Calendar size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No meetings found.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          {filtered.map((m) => {
            const badge = statusBadge(m.status);
            const upcoming = isUpcoming(m.meeting_date, m.status);

            return (
              <Link
                key={m.id}
                href={`/portal/advisory/meetings/${m.id}`}
                style={{ textDecoration: "none" }}
              >
                <div
                  style={{
                    ...glassCard,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    padding: "16px 20px",
                    transition: "all 0.2s ease",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                    <div
                      style={{
                        width: "44px",
                        height: "44px",
                        borderRadius: "12px",
                        background: "rgba(108,99,255,0.1)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Calendar size={20} style={{ color: "#00A651" }} />
                    </div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                        {m.meeting_type}
                      </div>
                      <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "2px", display: "flex", alignItems: "center", gap: "8px" }}>
                        <Clock size={12} />
                        {formatMeetingDate(m.meeting_date)}
                        {m.duration_minutes && ` (${m.duration_minutes} min)`}
                        {m.adviser_name && (
                          <span style={{ marginLeft: "4px" }}>with {m.adviser_name}</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span
                      style={{
                        padding: "4px 10px",
                        borderRadius: "6px",
                        fontSize: "12px",
                        fontWeight: 600,
                        background: badge.bg,
                        color: badge.color,
                        textTransform: "capitalize",
                      }}
                    >
                      {m.status.replace(/_/g, " ")}
                    </span>
                    {upcoming && m.teams_meeting_url && (
                      <a
                        href={m.teams_meeting_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: "6px",
                          padding: "6px 12px",
                          borderRadius: "8px",
                          background: "rgba(108,99,255,0.15)",
                          color: "#00A651",
                          fontSize: "12px",
                          fontWeight: 600,
                          textDecoration: "none",
                          border: "1px solid rgba(108,99,255,0.2)",
                        }}
                      >
                        <Video size={14} />
                        Join
                      </a>
                    )}
                  </div>
                </div>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}
