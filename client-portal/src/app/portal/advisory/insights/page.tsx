"use client";

import { useCallback, useEffect, useState } from "react";
import { Calendar, CheckCircle, Lightbulb, ListChecks } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui-shadcn/accordion";
import { Card } from "@/components/ui-shadcn/card";

interface MeetingInsight {
  id: string;
  meeting_id: string;
  summary: string | null;
  priorities: string[] | null;
  action_items: string[] | null;
  next_steps: string | null;
  meeting: {
    scheduled_at: string;
    meeting_type: string;
    adviser: { full_name: string } | null;
  };
}

export default function AdvisoryInsights() {
  const supabase = createClient();
  const [insights, setInsights] = useState<MeetingInsight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchInsights = useCallback(async () => {
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

    const { data: meetingData, error: insightErr } = await supabase
      .from("fa_meetings")
      .select("*,insights:fa_meeting_insights(*),adviser:fa_advisers(full_name)")
      .eq("client_id", client.id)
      .order("scheduled_at", { ascending: false });

    if (insightErr) {
      setError(insightErr.message);
      setLoading(false);
      return;
    }

    const normalized: MeetingInsight[] = [];
    for (const m of meetingData || []) {
      const meetingInsights = Array.isArray(m.insights) ? m.insights : [];
      for (const ins of meetingInsights) {
        normalized.push({
          ...ins,
          meeting: {
            scheduled_at: m.scheduled_at,
            meeting_type: m.meeting_type,
            adviser: m.adviser,
          },
        });
      }
    }

    setInsights(normalized);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchInsights();
  }, [fetchInsights]);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Meeting insights" description="Key takeaways and action items from your advisory meetings." />
        <LoadingState variant="card" rows={4} />
      </div>
    );
  }
  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Meeting insights" description="Key takeaways and action items from your advisory meetings." />
        <ErrorState title="Unable to load insights" description={error} onRetry={fetchInsights} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Advisory"
        title="Meeting insights"
        description="Key takeaways and action items from your advisory meetings."
      />

      {insights.length === 0 ? (
        <EmptyState
          icon={<Lightbulb className="size-5" />}
          title="No insights yet"
          description="Insights from your advisory meetings will appear here once they're published."
        />
      ) : (
        <Card variant="default" padding="none">
          <Accordion type="single" collapsible className="divide-y divide-[var(--border-subtle)]">
            {insights.map((insight) => {
              const meeting = insight.meeting;
              return (
                <AccordionItem key={insight.id} value={insight.id} className="border-b-0 px-5">
                  <AccordionTrigger className="py-4 hover:no-underline">
                    <div className="flex items-center gap-3 min-w-0 flex-1 pr-2">
                      <span className="grid place-items-center size-10 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)] shrink-0">
                        <Lightbulb className="size-4" aria-hidden />
                      </span>
                      <div className="min-w-0 text-left">
                        <p className="text-sm font-semibold text-foreground capitalize">
                          {meeting?.meeting_type?.replace(/_/g, " ") || "Meeting"}
                        </p>
                        <p className="flex items-center gap-1.5 text-xs text-[var(--text-dim)] mt-0.5">
                          <Calendar className="size-3" />
                          {meeting?.scheduled_at
                            ? new Date(meeting.scheduled_at).toLocaleDateString("en-ZA", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })
                            : "—"}
                          {meeting?.adviser?.full_name ? ` · ${meeting.adviser.full_name}` : ""}
                        </p>
                      </div>
                    </div>
                  </AccordionTrigger>
                  <AccordionContent className="pb-5 pt-0">
                    <div className="flex flex-col gap-4">
                      {insight.summary ? (
                        <InsightSection title="Summary">
                          <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                            {insight.summary}
                          </p>
                        </InsightSection>
                      ) : null}

                      {insight.priorities && insight.priorities.length > 0 ? (
                        <InsightSection
                          title="Priorities"
                          icon={<ListChecks className="size-3.5 text-[var(--warning)]" />}
                        >
                          <ul className="flex flex-col gap-1.5">
                            {insight.priorities.map((p, i) => (
                              <li
                                key={i}
                                className="flex items-start gap-2 text-sm text-[var(--text-muted)]"
                              >
                                <span className="font-bold text-[var(--warning)] shrink-0">
                                  {i + 1}.
                                </span>
                                {p}
                              </li>
                            ))}
                          </ul>
                        </InsightSection>
                      ) : null}

                      {insight.action_items && insight.action_items.length > 0 ? (
                        <InsightSection
                          title="Action items"
                          icon={<CheckCircle className="size-3.5 text-[var(--accent-teal)]" />}
                        >
                          <ul className="flex flex-col gap-1.5">
                            {insight.action_items.map((item, i) => (
                              <li
                                key={i}
                                className="flex items-center gap-2 text-sm text-[var(--text-muted)]"
                              >
                                <CheckCircle className="size-3 text-[var(--accent-teal)] shrink-0" />
                                {item}
                              </li>
                            ))}
                          </ul>
                        </InsightSection>
                      ) : null}

                      {insight.next_steps ? (
                        <InsightSection title="Next steps">
                          <p className="text-sm text-[var(--text-muted)] leading-relaxed">
                            {insight.next_steps}
                          </p>
                        </InsightSection>
                      ) : null}
                    </div>
                  </AccordionContent>
                </AccordionItem>
              );
            })}
          </Accordion>
        </Card>
      )}
    </div>
  );
}

function InsightSection({
  title,
  icon,
  children,
}: {
  title: string;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h4 className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-muted)] mb-2">
        {icon}
        {title}
      </h4>
      {children}
    </div>
  );
}
