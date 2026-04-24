"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  ArrowLeft,
  Calendar,
  CheckCircle,
  Clock,
  ListChecks,
  Mic,
  User,
  Video,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";

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

function statusTone(status: string): "info" | "success" | "danger" | "warning" | "neutral" {
  const s = status.toLowerCase();
  if (s === "scheduled") return "info";
  if (s === "confirmed" || s === "completed") return "success";
  if (s === "cancelled") return "danger";
  if (s === "no_show") return "warning";
  return "neutral";
}

function recordingDisplay(status: string | null): { tone: "success" | "warning" | "neutral"; label: string } | null {
  if (!status) return null;
  const s = status.toLowerCase();
  if (s === "available") return { tone: "success", label: "Recording available" };
  if (s === "processing") return { tone: "warning", label: "Processing" };
  return { tone: "neutral", label: status };
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
    if (insightData) setInsights(insightData);
    setLoading(false);
  }, [supabase, meetingId]);

  useEffect(() => {
    fetchMeeting();
  }, [fetchMeeting]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/portal/advisory/meetings" className="gap-1.5">
            <ArrowLeft className="size-3.5" />
            Back to meetings
          </Link>
        </Button>
        <LoadingState variant="card" rows={5} />
      </div>
    );
  }

  if (error || !meeting) {
    return (
      <div className="flex flex-col gap-6">
        <Button asChild variant="ghost" size="sm" className="self-start">
          <Link href="/portal/advisory/meetings" className="gap-1.5">
            <ArrowLeft className="size-3.5" />
            Back to meetings
          </Link>
        </Button>
        <ErrorState title="Meeting not found" description={error ?? "The meeting may have been removed."} />
      </div>
    );
  }

  const recording = recordingDisplay(meeting.recording_status);
  const isUpcoming = new Date(meeting.scheduled_at) > new Date() && meeting.status !== "completed";

  return (
    <div className="flex flex-col gap-6">
      <Button asChild variant="ghost" size="sm" className="self-start">
        <Link href="/portal/advisory/meetings" className="gap-1.5">
          <ArrowLeft className="size-3.5" />
          Back to meetings
        </Link>
      </Button>

      <PageHeader
        eyebrow="Advisory · Meeting"
        title={meeting.meeting_type.replace(/_/g, " ")}
        description={`${new Date(meeting.scheduled_at).toLocaleDateString("en-ZA", { weekday: "long", day: "numeric", month: "long", year: "numeric" })}`}
        actions={
          <Badge tone={statusTone(meeting.status)} appearance="soft" className="capitalize">
            {meeting.status.replace(/_/g, " ")}
          </Badge>
        }
      />

      {/* Meeting details card */}
      <Card variant="default" padding="lg">
        <CardContent className="flex flex-col md:flex-row md:items-start md:justify-between gap-5">
          <div className="flex flex-col gap-2">
            <Row
              icon={<Calendar className="size-4" />}
              text={new Date(meeting.scheduled_at).toLocaleDateString("en-ZA", {
                weekday: "long",
                day: "numeric",
                month: "long",
                year: "numeric",
              })}
            />
            <Row
              icon={<Clock className="size-4" />}
              text={`${new Date(meeting.scheduled_at).toLocaleTimeString("en-ZA", {
                hour: "2-digit",
                minute: "2-digit",
              })}${meeting.duration_minutes ? ` · ${meeting.duration_minutes} min` : ""}`}
            />
            {meeting.adviser?.full_name ? (
              <Row icon={<User className="size-4" />} text={`Adviser: ${meeting.adviser.full_name}`} />
            ) : null}
          </div>

          <div className="flex flex-col items-start md:items-end gap-3">
            {recording ? (
              <Badge tone={recording.tone} appearance="soft" size="sm">
                <Mic className="size-3" />
                {recording.label}
              </Badge>
            ) : null}
            {isUpcoming && meeting.teams_meeting_url ? (
              <Button asChild variant="default">
                <a href={meeting.teams_meeting_url} target="_blank" rel="noopener noreferrer">
                  <Video className="size-4" />
                  Join meeting
                </a>
              </Button>
            ) : null}
          </div>
        </CardContent>

        {meeting.notes ? (
          <CardContent className="pt-4 border-t border-[var(--border-subtle)] mt-5">
            <h3 className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)] mb-2">
              Notes
            </h3>
            <p className="text-sm text-[var(--text-muted)] leading-relaxed">{meeting.notes}</p>
          </CardContent>
        ) : null}
      </Card>

      {/* Insights */}
      {insights ? (
        <div className="flex flex-col gap-4">
          {insights.summary ? (
            <InsightCard title="Meeting summary">
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">{insights.summary}</p>
            </InsightCard>
          ) : null}

          {insights.priorities && insights.priorities.length > 0 ? (
            <InsightCard
              title="Priorities"
              icon={<ListChecks className="size-4 text-[var(--warning)]" />}
            >
              <ul className="flex flex-col gap-2">
                {insights.priorities.map((p, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-[var(--text-muted)]">
                    <span className="text-[var(--warning)] font-bold shrink-0">{i + 1}.</span>
                    {p}
                  </li>
                ))}
              </ul>
            </InsightCard>
          ) : null}

          {insights.action_items && insights.action_items.length > 0 ? (
            <InsightCard
              title="Action items"
              icon={<CheckCircle className="size-4 text-[var(--accent-teal)]" />}
            >
              <ul className="flex flex-col gap-2">
                {insights.action_items.map((item, i) => (
                  <li key={i} className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
                    <CheckCircle className="size-3.5 text-[var(--accent-teal)] shrink-0" />
                    {item}
                  </li>
                ))}
              </ul>
            </InsightCard>
          ) : null}

          {insights.next_steps ? (
            <InsightCard title="Next steps">
              <p className="text-sm text-[var(--text-muted)] leading-relaxed">{insights.next_steps}</p>
            </InsightCard>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Row({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-[var(--text-muted)]">
      <span className="text-[var(--text-dim)]">{icon}</span>
      {text}
    </div>
  );
}

function InsightCard({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <Card variant="default" padding="lg">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent className="pt-3">{children}</CardContent>
    </Card>
  );
}
