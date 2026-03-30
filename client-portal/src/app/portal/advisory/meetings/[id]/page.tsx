"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import Link from "next/link";
import {
  ArrowLeft,
  Calendar,
  Clock,
  User,
  Video,
  Mic,
  CheckCircle,
  ListChecks,
} from "lucide-react";

interface MeetingDetail {
  id: string;
  scheduled_at: string;
  meeting_type: string;
  status: string;
  adviser: { full_name: string } | null;
  teams_meeting_url: string | null;
  duration_minutes: number | null;
  notes: string | null;
  recording_status: string | null;
}

interface MeetingInsight {
  id: string;
  summary: string | null;
  priorities: string[] | null;
  action_items: string[] | null;
  next_steps: string | null;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

function statusBadge(status: string) {
  const map: Record<string, { color: string; bg: string }> = {
    scheduled: { color: "#00A651", bg: "rgba(108,99,255,0.1)" },
    confirmed: { color: "#00D4AA", bg: "rgba(0,212,170,0.1)" },
    completed: { color: "#10B981", bg: "rgba(16,185,129,0.1)" },
    cancelled: { color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
    no_show: { color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
  };
  return map[status.toLowerCase()] || { color: "#6B7280", bg: "rgba(107,114,128,0.1)" };
}

function recordingBadge(status: string | null) {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "available") return { color: "#10B981", label: "Recording Available" };
  if (s === "processing") return { color: "#F59E0B", label: "Processing" };
  return { color: "#6B7280", label: status };
}

export default function MeetingDetailPage() {
  const params = useParams();
  const meetingId = params.id as string;
  const supabase = createClient();
  const [meeting, setMeeting] = useState<MeetingDetail | null>(null);
  const [insights, setInsights] = useState<MeetingInsight | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMeeting = useCallback(async () => {
    setLoading(true);

    const { data: meetingData, error: meetingErr } = await supabase
      .from("fa_meetings")
      .select("*,adviser:fa_advisers(full_name),insights:fa_meeting_insights(*)")
      .eq("id", meetingId)
      .single();

    if (meetingErr || !meetingData) {
      setError("Meeting not found.");
      setLoading(false);
      return;
    }

    setMeeting(meetingData);

    const insightData = Array.isArray(meetingData.insights) && meetingData.insights.length > 0
      ? meetingData.insights[0]
      : null;

    if (insightData) {
      setInsights(insightData);
    }

    setLoading(false);
  }, [supabase, meetingId]);

  useEffect(() => {
    fetchMeeting();
  }, [fetchMeeting]);

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

  if (error || !meeting) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error || "Meeting not found."}</p>
        <Link href="/portal/advisory/meetings" style={{ color: "#00A651", fontSize: "13px", marginTop: "8px", display: "inline-block" }}>
          Back to Meetings
        </Link>
      </div>
    );
  }

  const badge = statusBadge(meeting.status);
  const recording = recordingBadge(meeting.recording_status);
  const isUpcoming = new Date(meeting.scheduled_at) > new Date() && meeting.status !== "completed";

  return (
    <div>
      {/* Back link */}
      <Link
        href="/portal/advisory/meetings"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "6px",
          color: "#6B7280",
          fontSize: "13px",
          textDecoration: "none",
          marginBottom: "20px",
        }}
      >
        <ArrowLeft size={14} />
        Back to Meetings
      </Link>

      {/* Meeting Header */}
      <div style={{ ...glassCard, marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
          <div>
            <h1 style={{ fontSize: "22px", fontWeight: 600, color: "#fff", marginBottom: "8px" }}>
              {meeting.meeting_type}
            </h1>
            <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#B0B8C8", fontSize: "14px" }}>
                <Calendar size={14} />
                {new Date(meeting.scheduled_at).toLocaleDateString("en-ZA", {
                  weekday: "long",
                  day: "numeric",
                  month: "long",
                  year: "numeric",
                })}
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#B0B8C8", fontSize: "14px" }}>
                <Clock size={14} />
                {new Date(meeting.scheduled_at).toLocaleTimeString("en-ZA", {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
                {meeting.duration_minutes && ` (${meeting.duration_minutes} minutes)`}
              </div>
              {meeting.adviser?.full_name && (
                <div style={{ display: "flex", alignItems: "center", gap: "8px", color: "#B0B8C8", fontSize: "14px" }}>
                  <User size={14} />
                  Adviser: {meeting.adviser.full_name}
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "8px" }}>
            <span
              style={{
                padding: "4px 12px",
                borderRadius: "6px",
                fontSize: "12px",
                fontWeight: 600,
                background: badge.bg,
                color: badge.color,
                textTransform: "capitalize",
              }}
            >
              {meeting.status.replace(/_/g, " ")}
            </span>

            {recording && (
              <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", color: recording.color }}>
                <Mic size={12} />
                {recording.label}
              </div>
            )}

            {isUpcoming && meeting.teams_meeting_url && (
              <a
                href={meeting.teams_meeting_url}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "8px",
                  padding: "10px 18px",
                  borderRadius: "10px",
                  background: "linear-gradient(135deg, #00A651, #5B5FC7)",
                  color: "#fff",
                  fontSize: "14px",
                  fontWeight: 600,
                  textDecoration: "none",
                }}
              >
                <Video size={16} />
                Join Meeting
              </a>
            )}
          </div>
        </div>

        {meeting.notes && (
          <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
            <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#B0B8C8", marginBottom: "8px" }}>Notes</h3>
            <p style={{ fontSize: "14px", color: "#9CA3AF", lineHeight: "1.6" }}>{meeting.notes}</p>
          </div>
        )}
      </div>

      {/* Insights */}
      {insights && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {insights.summary && (
            <div style={glassCard}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "12px" }}>
                Meeting Summary
              </h3>
              <p style={{ fontSize: "14px", color: "#B0B8C8", lineHeight: "1.7" }}>{insights.summary}</p>
            </div>
          )}

          {insights.priorities && insights.priorities.length > 0 && (
            <div style={glassCard}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                <ListChecks size={16} style={{ color: "#F59E0B" }} />
                Priorities
              </h3>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
                {insights.priorities.map((p, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      gap: "10px",
                      fontSize: "14px",
                      color: "#B0B8C8",
                    }}
                  >
                    <span style={{ color: "#F59E0B", fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                    {p}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insights.action_items && insights.action_items.length > 0 && (
            <div style={glassCard}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                <CheckCircle size={16} style={{ color: "#00D4AA" }} />
                Action Items
              </h3>
              <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "8px" }}>
                {insights.action_items.map((item, i) => (
                  <li
                    key={i}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "10px",
                      fontSize: "14px",
                      color: "#B0B8C8",
                    }}
                  >
                    <CheckCircle size={14} style={{ color: "#00D4AA", flexShrink: 0 }} />
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {insights.next_steps && (
            <div style={glassCard}>
              <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "12px" }}>
                Next Steps
              </h3>
              <p style={{ fontSize: "14px", color: "#B0B8C8", lineHeight: "1.7" }}>
                {insights.next_steps}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
