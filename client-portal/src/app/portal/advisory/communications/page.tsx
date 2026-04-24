"use client";

import { useCallback, useEffect, useState } from "react";
import {
  ArrowDownLeft,
  ArrowUpRight,
  Globe,
  Mail,
  MessageCircle,
  Video,
  type LucideIcon,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";

interface FaCommunication {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  content: string | null;
  created_at: string;
  status: string | null;
}

const CHANNEL: Record<string, { icon: LucideIcon; color: string; label: string }> = {
  email:    { icon: Mail,          color: "var(--accent-teal)",   label: "Email" },
  whatsapp: { icon: MessageCircle, color: "var(--accent-teal)",   label: "WhatsApp" },
  teams:    { icon: Video,         color: "var(--accent-purple)", label: "Teams" },
  portal:   { icon: Globe,         color: "var(--accent-coral)",  label: "Portal" },
};

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
    groups[dayKey] = [...(groups[dayKey] ?? []), c];
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

    const { data: portalClient } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", userData.user.id)
      .single();
    if (!portalClient) {
      setError("No portal account found");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", portalClient.id)
      .single();
    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: commData, error: commErr } = await supabase
      .from("fa_communications")
      .select("id, channel, direction, subject, content, created_at, status")
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
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Communications" description="Your communication history with your advisory team." />
        <LoadingState variant="list" rows={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Communications" description="Your communication history with your advisory team." />
        <ErrorState title="Unable to load communications" description={error} onRetry={fetchCommunications} />
      </div>
    );
  }

  const grouped = groupByDay(communications);
  const sortedDays = Object.keys(grouped).sort((a, b) => b.localeCompare(a));

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Advisory"
        title="Communications"
        description="Your communication history with your advisory team."
      />

      {communications.length === 0 ? (
        <EmptyState icon={<MessageCircle className="size-5" />} title="No communications yet" />
      ) : (
        <div className="flex flex-col gap-8">
          {sortedDays.map((day) => {
            const dayComms = grouped[day];
            return (
              <section key={day}>
                <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)] pb-2 mb-3 border-b border-[var(--border-subtle)]">
                  {formatRelativeDay(dayComms[0].created_at)}
                </h3>
                <Card variant="default" padding="md">
                  <ul className="relative pl-8">
                    <span
                      aria-hidden
                      className="absolute left-[15px] top-3 bottom-3 w-px bg-[var(--border-subtle)]"
                    />
                    {dayComms.map((comm) => {
                      const config = CHANNEL[comm.channel.toLowerCase()] || CHANNEL.portal;
                      const Icon = config.icon;
                      const isSent =
                        comm.direction.toLowerCase() === "sent" ||
                        comm.direction.toLowerCase() === "outbound";
                      return (
                        <li key={comm.id} className="relative py-3">
                          <span
                            aria-hidden
                            className="absolute -left-[17px] top-3 grid place-items-center size-8 rounded-[var(--radius-sm)] ring-4 ring-[var(--bg-card)]"
                            style={{
                              background: `color-mix(in srgb, ${config.color} 12%, transparent)`,
                              color: config.color,
                            }}
                          >
                            <Icon className="size-3.5" aria-hidden />
                          </span>
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-sm font-semibold text-foreground">
                                  {comm.subject || `${config.label} ${comm.direction}`}
                                </span>
                                <Badge
                                  tone={isSent ? "info" : "success"}
                                  appearance="soft"
                                  size="sm"
                                >
                                  {isSent ? <ArrowUpRight className="size-3" /> : <ArrowDownLeft className="size-3" />}
                                  {isSent ? "Sent" : "Received"}
                                </Badge>
                              </div>
                              {comm.content ? (
                                <p className="text-sm text-[var(--text-muted)] mt-1 line-clamp-1">
                                  {comm.content}
                                </p>
                              ) : null}
                              <p className="text-xs text-[var(--text-dim)] mt-1">
                                {new Date(comm.created_at).toLocaleTimeString("en-ZA", {
                                  hour: "2-digit",
                                  minute: "2-digit",
                                })}{" "}
                                · via {config.label}
                              </p>
                            </div>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </Card>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
