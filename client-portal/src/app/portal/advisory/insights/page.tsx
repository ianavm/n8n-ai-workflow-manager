"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  Lightbulb,
  Calendar,
  ListChecks,
  CheckCircle,
  ArrowRight,
} from "lucide-react";

interface MeetingInsight {
  id: string;
  meeting_id: string;
  summary: string | null;
  priorities: string[] | null;
  action_items: string[] | null;
  next_steps: string[] | null;
  meeting: {
    meeting_date: string;
    meeting_type: string;
    adviser_name: string | null;
  };
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

export default function AdvisoryInsights() {
  const supabase = createClient();
  const [insights, setInsights] = useState<MeetingInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const fetchInsights = useCallback(async () => {
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

    const { data: insightData, error: insightErr } = await supabase
      .from("fa_meeting_insights")
      .select(`
        id,
        meeting_id,
        summary,
        priorities,
        action_items,
        next_steps,
        meeting:fa_meetings!inner (
          meeting_date,
          meeting_type,
          adviser_name
        )
      `)
      .eq("fa_meetings.client_id", client.id)
      .order("created_at", { ascending: false });

    if (insightErr) {
      setError(insightErr.message);
      setLoading(false);
      return;
    }

    // Normalize the joined meeting data
    const normalized = (insightData || []).map((row: Record<string, unknown>) => ({
      ...row,
      meeting: Array.isArray(row.meeting) ? row.meeting[0] : row.meeting,
    })) as MeetingInsight[];

    setInsights(normalized);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
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

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Meeting Insights</h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          Key takeaways and action items from your advisory meetings.
        </p>
      </div>

      {insights.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <Lightbulb size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No meeting insights available yet.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {insights.map((insight) => {
            const isExpanded = expandedId === insight.id;
            const meeting = insight.meeting;

            return (
              <div key={insight.id} style={glassCard}>
                {/* Header - clickable to expand */}
                <button
                  onClick={() => setExpandedId(isExpanded ? null : insight.id)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    width: "100%",
                    background: "none",
                    border: "none",
                    cursor: "pointer",
                    padding: 0,
                    fontFamily: "inherit",
                    textAlign: "left",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "14px" }}>
                    <div
                      style={{
                        width: "40px",
                        height: "40px",
                        borderRadius: "10px",
                        background: "rgba(108,99,255,0.1)",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Lightbulb size={18} style={{ color: "#6C63FF" }} />
                    </div>
                    <div>
                      <div style={{ fontSize: "14px", fontWeight: 600, color: "#fff" }}>
                        {meeting?.meeting_type || "Meeting"}
                      </div>
                      <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "2px", display: "flex", alignItems: "center", gap: "6px" }}>
                        <Calendar size={11} />
                        {meeting?.meeting_date
                          ? new Date(meeting.meeting_date).toLocaleDateString("en-ZA", {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })
                          : "---"}
                        {meeting?.adviser_name && ` - ${meeting.adviser_name}`}
                      </div>
                    </div>
                  </div>
                  <ArrowRight
                    size={16}
                    style={{
                      color: "#6B7280",
                      transition: "transform 0.2s ease",
                      transform: isExpanded ? "rotate(90deg)" : "rotate(0deg)",
                    }}
                  />
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px solid rgba(255,255,255,0.06)" }}>
                    {insight.summary && (
                      <div style={{ marginBottom: "16px" }}>
                        <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#B0B8C8", marginBottom: "8px" }}>
                          Summary
                        </h4>
                        <p style={{ fontSize: "14px", color: "#9CA3AF", lineHeight: "1.7" }}>
                          {insight.summary}
                        </p>
                      </div>
                    )}

                    {insight.priorities && insight.priorities.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#B0B8C8", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <ListChecks size={13} style={{ color: "#F59E0B" }} />
                          Priorities
                        </h4>
                        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "6px" }}>
                          {insight.priorities.map((p, i) => (
                            <li key={i} style={{ fontSize: "13px", color: "#B0B8C8", display: "flex", alignItems: "flex-start", gap: "8px" }}>
                              <span style={{ color: "#F59E0B", fontWeight: 700, flexShrink: 0 }}>{i + 1}.</span>
                              {p}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {insight.action_items && insight.action_items.length > 0 && (
                      <div style={{ marginBottom: "16px" }}>
                        <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#B0B8C8", marginBottom: "8px", display: "flex", alignItems: "center", gap: "6px" }}>
                          <CheckCircle size={13} style={{ color: "#00D4AA" }} />
                          Action Items
                        </h4>
                        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "6px" }}>
                          {insight.action_items.map((item, i) => (
                            <li key={i} style={{ fontSize: "13px", color: "#B0B8C8", display: "flex", alignItems: "center", gap: "8px" }}>
                              <CheckCircle size={12} style={{ color: "#00D4AA", flexShrink: 0 }} />
                              {item}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {insight.next_steps && insight.next_steps.length > 0 && (
                      <div>
                        <h4 style={{ fontSize: "13px", fontWeight: 600, color: "#B0B8C8", marginBottom: "8px" }}>
                          Next Steps
                        </h4>
                        <ul style={{ margin: 0, padding: 0, listStyle: "none", display: "flex", flexDirection: "column", gap: "6px" }}>
                          {insight.next_steps.map((step, i) => (
                            <li key={i} style={{ fontSize: "13px", color: "#B0B8C8", display: "flex", alignItems: "flex-start", gap: "8px" }}>
                              <span style={{ color: "#6C63FF", flexShrink: 0 }}>&rarr;</span>
                              {step}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
