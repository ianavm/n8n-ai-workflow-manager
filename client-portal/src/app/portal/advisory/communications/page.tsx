"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  MessageCircle,
  Mail,
  Video,
  Globe,
  ArrowUpRight,
  ArrowDownLeft,
} from "lucide-react";

interface FaCommunication {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  body_preview: string | null;
  created_at: string;
  status: string | null;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

const channelConfig: Record<string, { icon: typeof Mail; color: string; label: string }> = {
  email: { icon: Mail, color: "#00A651", label: "Email" },
  whatsapp: { icon: MessageCircle, color: "#25D366", label: "WhatsApp" },
  teams: { icon: Video, color: "#5B5FC7", label: "Teams" },
  portal: { icon: Globe, color: "#00D4AA", label: "Portal" },
};

function formatDateTime(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeDay(dateStr: string): string {
  const d = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const targetDay = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.floor((today.getTime() - targetDay.getTime()) / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  return d.toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "short" });
}

function groupByDay(comms: FaCommunication[]): Record<string, FaCommunication[]> {
  const groups: Record<string, FaCommunication[]> = {};
  for (const c of comms) {
    const dayKey = new Date(c.created_at).toISOString().split("T")[0];
    if (!groups[dayKey]) {
      groups[dayKey] = [];
    }
    groups[dayKey] = [...groups[dayKey], c];
  }
  return groups;
}

export default function AdvisoryCommunications() {
  const supabase = createClient();
  const [communications, setCommunications] = useState<FaCommunication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCommunications = useCallback(async () => {
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

    const { data: commData, error: commErr } = await supabase
      .from("fa_communications")
      .select("id, channel, direction, subject, body_preview, created_at, status")
      .eq("client_id", client.id)
      .order("created_at", { ascending: false })
      .limit(50);

    if (commErr) {
      setError(commErr.message);
      setLoading(false);
      return;
    }

    setCommunications(commData || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchCommunications();
  }, [fetchCommunications]);

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

  const grouped = groupByDay(communications);
  const sortedDays = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Communications</h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          Your communication history with your advisory team.
        </p>
      </div>

      {communications.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <MessageCircle size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No communications yet.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "24px" }}>
          {sortedDays.map((day) => {
            const dayComms = grouped[day];

            return (
              <div key={day}>
                {/* Day header */}
                <div
                  style={{
                    fontSize: "12px",
                    fontWeight: 600,
                    color: "#6B7280",
                    textTransform: "uppercase",
                    letterSpacing: "1px",
                    marginBottom: "12px",
                    paddingBottom: "8px",
                    borderBottom: "1px solid rgba(255,255,255,0.04)",
                  }}
                >
                  {formatRelativeDay(dayComms[0].created_at)}
                </div>

                {/* Timeline items */}
                <div style={{ display: "flex", flexDirection: "column", gap: "0" }}>
                  {dayComms.map((comm, idx) => {
                    const config = channelConfig[comm.channel.toLowerCase()] || channelConfig.portal;
                    const ChannelIcon = config.icon;
                    const isSent = comm.direction.toLowerCase() === "sent" || comm.direction.toLowerCase() === "outbound";
                    const isLast = idx === dayComms.length - 1;

                    return (
                      <div
                        key={comm.id}
                        style={{
                          display: "flex",
                          gap: "16px",
                          paddingBottom: isLast ? "0" : "0",
                        }}
                      >
                        {/* Timeline indicator */}
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            flexShrink: 0,
                            width: "32px",
                          }}
                        >
                          <div
                            style={{
                              width: "32px",
                              height: "32px",
                              borderRadius: "8px",
                              background: `${config.color}15`,
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <ChannelIcon size={14} style={{ color: config.color }} />
                          </div>
                          {!isLast && (
                            <div
                              style={{
                                width: "2px",
                                flex: 1,
                                background: "rgba(255,255,255,0.06)",
                                minHeight: "16px",
                              }}
                            />
                          )}
                        </div>

                        {/* Content */}
                        <div
                          style={{
                            flex: 1,
                            paddingBottom: isLast ? "0" : "16px",
                            minWidth: 0,
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                            <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
                              {comm.subject || `${config.label} ${comm.direction}`}
                            </span>
                            <span
                              style={{
                                display: "inline-flex",
                                alignItems: "center",
                                gap: "4px",
                                fontSize: "11px",
                                fontWeight: 500,
                                color: isSent ? "#00A651" : "#00D4AA",
                                padding: "1px 6px",
                                borderRadius: "4px",
                                background: isSent ? "rgba(108,99,255,0.1)" : "rgba(0,212,170,0.1)",
                              }}
                            >
                              {isSent ? <ArrowUpRight size={10} /> : <ArrowDownLeft size={10} />}
                              {isSent ? "Sent" : "Received"}
                            </span>
                          </div>

                          {comm.body_preview && (
                            <p
                              style={{
                                fontSize: "13px",
                                color: "#6B7280",
                                lineHeight: "1.5",
                                margin: "0 0 4px 0",
                                overflow: "hidden",
                                textOverflow: "ellipsis",
                                whiteSpace: "nowrap",
                                maxWidth: "500px",
                              }}
                            >
                              {comm.body_preview}
                            </p>
                          )}

                          <span style={{ fontSize: "11px", color: "#4B5563" }}>
                            {new Date(comm.created_at).toLocaleTimeString("en-ZA", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                            {" via "}
                            {config.label}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
