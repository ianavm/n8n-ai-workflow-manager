"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Calendar, Clock, Video } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card } from "@/components/ui-shadcn/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui-shadcn/tabs";

interface FaMeeting {
  id: string;
  scheduled_at: string;
  meeting_type: string;
  status: string;
  adviser: { full_name: string } | null;
  teams_meeting_url: string | null;
  duration_minutes: number | null;
}

type MeetingFilter = "all" | "upcoming" | "completed";

function statusTone(status: string): "info" | "success" | "danger" | "warning" | "neutral" {
  const s = status.toLowerCase();
  if (s === "scheduled") return "info";
  if (s === "confirmed") return "success";
  if (s === "completed") return "success";
  if (s === "cancelled") return "danger";
  if (s === "no_show") return "warning";
  return "neutral";
}

function formatMeetingDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
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

    const { data: meetingData, error: meetingErr } = await supabase
      .from("fa_meetings")
      .select("*,adviser:fa_advisers(full_name)")
      .eq("client_id", client.id)
      .order("scheduled_at", { ascending: false });

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
    if (filter === "upcoming") return isUpcoming(m.scheduled_at, m.status);
    if (filter === "completed") return m.status === "completed";
    return true;
  });

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Meetings" description="Your advisory meetings and consultations." />
        <LoadingState variant="list" rows={4} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Meetings" description="Your advisory meetings and consultations." />
        <ErrorState title="Unable to load meetings" description={error} onRetry={fetchMeetings} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Advisory"
        title="Meetings"
        description="Your advisory meetings and consultations."
        actions={
          <Tabs value={filter} onValueChange={(v) => setFilter(v as MeetingFilter)}>
            <TabsList variant="default">
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="upcoming">Upcoming</TabsTrigger>
              <TabsTrigger value="completed">Completed</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      {filtered.length === 0 ? (
        <EmptyState icon={<Calendar className="size-5" />} title="No meetings found" />
      ) : (
        <ul className="flex flex-col gap-3">
          {filtered.map((m) => {
            const upcoming = isUpcoming(m.scheduled_at, m.status);
            return (
              <li key={m.id}>
                <Link href={`/portal/advisory/meetings/${m.id}`}>
                  <Card variant="interactive" padding="md">
                    <div className="flex items-center justify-between gap-4">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="grid place-items-center size-10 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-teal)_12%,transparent)] text-[var(--accent-teal)] shrink-0">
                          <Calendar className="size-4" aria-hidden />
                        </span>
                        <div className="min-w-0">
                          <p className="text-sm font-semibold text-foreground capitalize">
                            {m.meeting_type.replace(/_/g, " ")}
                          </p>
                          <p className="flex flex-wrap items-center gap-x-2 text-xs text-[var(--text-dim)] mt-0.5">
                            <span className="inline-flex items-center gap-1">
                              <Clock className="size-3" />
                              {formatMeetingDate(m.scheduled_at)}
                            </span>
                            {m.duration_minutes ? <span>({m.duration_minutes} min)</span> : null}
                            {m.adviser?.full_name ? <span>with {m.adviser.full_name}</span> : null}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <Badge tone={statusTone(m.status)} appearance="soft" size="sm" className="capitalize">
                          {m.status.replace(/_/g, " ")}
                        </Badge>
                        {upcoming && m.teams_meeting_url ? (
                          <Button
                            asChild
                            variant="outline"
                            size="sm"
                            onClick={(e) => e.stopPropagation()}
                          >
                            <a href={m.teams_meeting_url} target="_blank" rel="noopener noreferrer">
                              <Video className="size-3.5" />
                              Join
                            </a>
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  </Card>
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
