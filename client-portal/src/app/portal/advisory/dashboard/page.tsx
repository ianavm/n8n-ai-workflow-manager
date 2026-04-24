"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Calendar, CheckSquare, Heart, Package, Plus, Upload } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { KPIGrid } from "@/components/portal/KPIGrid";
import { StatCard } from "@/components/portal/StatCard";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";

interface RpcDashboardData {
  upcoming_meetings: number;
  pending_tasks: number;
  active_products: number;
  health_score: number;
  unread_comms: number;
  pipeline_stage: string;
}

interface FaMeeting {
  id: string;
  scheduled_at: string;
  meeting_type: string;
  status: string;
  teams_meeting_url: string | null;
  adviser: { full_name: string } | null;
}

interface FaCommunication {
  id: string;
  channel: string;
  direction: string;
  subject: string | null;
  created_at: string;
}

interface DashboardData {
  rpc: RpcDashboardData;
  upcoming_meetings: FaMeeting[];
  recent_activity: FaCommunication[];
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatRelativeTime(dateStr: string): string {
  const now = new Date();
  const d = new Date(dateStr);
  const diffMins = Math.floor((now.getTime() - d.getTime()) / 60000);
  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays}d ago`;
}

const CHANNEL_COLOR: Record<string, string> = {
  email: "var(--accent-teal)",
  whatsapp: "var(--accent-teal)",
  teams: "var(--accent-purple)",
  portal: "var(--accent-coral)",
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

    const { data: faClient } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", portalClient.id)
      .single();
    if (!faClient) {
      setError("No advisory profile linked to your account.");
      setLoading(false);
      return;
    }

    const { data: rpcData, error: rpcError } = await supabase.rpc(
      "fa_get_client_dashboard",
      { p_client_id: faClient.id },
    );
    if (rpcError) {
      setError(rpcError.message);
      setLoading(false);
      return;
    }

    const { data: meetingsData } = await supabase
      .from("fa_meetings")
      .select("*,adviser:fa_advisers(full_name)")
      .eq("client_id", faClient.id)
      .in("status", ["scheduled", "confirmed"])
      .order("scheduled_at", { ascending: true })
      .limit(3);

    const { data: activityData } = await supabase
      .from("fa_communications")
      .select("*")
      .eq("client_id", faClient.id)
      .order("created_at", { ascending: false })
      .limit(10);

    setData({
      rpc: rpcData,
      upcoming_meetings: meetingsData || [],
      recent_activity: activityData || [],
    });
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Advisory"
          title="Advisory dashboard"
          description="Your financial advisory overview at a glance."
        />
        <LoadingState variant="dashboard" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Advisory"
          title="Advisory dashboard"
          description="Your financial advisory overview at a glance."
        />
        <ErrorState title="Unable to load advisory data" description={error} onRetry={fetchDashboard} />
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Advisory"
        title="Advisory dashboard"
        description="Your financial advisory overview at a glance."
        actions={
          <>
            <Button asChild variant="default" size="sm">
              <Link href="/portal/advisory/meetings">
                <Plus className="size-3.5" />
                Request meeting
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link href="/portal/advisory/documents">
                <Upload className="size-3.5" />
                Upload document
              </Link>
            </Button>
          </>
        }
      />

      <KPIGrid cols={4}>
        <StatCard
          label="Upcoming meetings"
          value={data.rpc.upcoming_meetings}
          icon={<Calendar className="size-4" aria-hidden />}
          accent="teal"
        />
        <StatCard
          label="Pending tasks"
          value={data.rpc.pending_tasks}
          icon={<CheckSquare className="size-4" aria-hidden />}
          accent="warning"
        />
        <StatCard
          label="Active products"
          value={data.rpc.active_products}
          icon={<Package className="size-4" aria-hidden />}
          accent="teal"
        />
        <StatCard
          label="Health score"
          value={data.rpc.health_score}
          suffix="%"
          icon={<Heart className="size-4" aria-hidden />}
          accent="coral"
        />
      </KPIGrid>

      <section className="grid gap-4 lg:grid-cols-2">
        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Upcoming meetings</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {data.upcoming_meetings.length === 0 ? (
              <EmptyState inline title="No upcoming meetings" description="Request a meeting from the action above." />
            ) : (
              <ul className="flex flex-col gap-2.5">
                {data.upcoming_meetings.slice(0, 3).map((m) => (
                  <li
                    key={m.id}
                    className="flex items-center justify-between gap-3 p-3 rounded-[var(--radius-sm)] bg-[var(--bg-card)] border border-[var(--border-subtle)]"
                  >
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-foreground capitalize">
                        {m.meeting_type.replace("_", " ")}
                      </p>
                      <p className="text-xs text-[var(--text-dim)] mt-0.5">
                        {formatDate(m.scheduled_at)}
                      </p>
                    </div>
                    {m.teams_meeting_url ? (
                      <Button asChild variant="outline" size="sm">
                        <a href={m.teams_meeting_url} target="_blank" rel="noopener noreferrer">
                          Join
                        </a>
                      </Button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Recent activity</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            {data.recent_activity.length === 0 ? (
              <EmptyState inline title="No recent activity" />
            ) : (
              <ul className="flex flex-col divide-y divide-[var(--border-subtle)]">
                {data.recent_activity.slice(0, 10).map((a) => (
                  <li key={a.id} className="flex items-center gap-3 py-2.5">
                    <span
                      aria-hidden
                      className="size-2 rounded-full shrink-0"
                      style={{ background: CHANNEL_COLOR[a.channel] || "var(--text-dim)" }}
                    />
                    <span className="flex-1 min-w-0 text-sm text-foreground truncate">
                      {a.subject || `${a.channel} ${a.direction}`}
                    </span>
                    <span className="text-xs text-[var(--text-dim)] shrink-0">
                      {formatRelativeTime(a.created_at)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
