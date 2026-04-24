"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  CreditCard,
  HeartPulse,
  LifeBuoy,
  Lightbulb,
  Megaphone,
} from "lucide-react";
import { toast } from "sonner";

import { HealthGauge } from "@/components/dashboard/HealthGauge";
import { ComparisonArrow } from "@/components/dashboard/ComparisonArrow";
import { TrendChart } from "@/components/charts/TrendChart";

import { PageHeader } from "@/components/portal/PageHeader";
import { RiskBadge } from "@/components/portal/RiskBadge";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui-shadcn/card";

interface HealthCurrent {
  composite_score: number;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
  risk_level: string;
  trend: string;
}

interface HealthHistoryEntry {
  score_date: string;
  composite_score: number;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
}

interface HealthData {
  current: HealthCurrent | null;
  history: HealthHistoryEntry[];
  alerts: unknown[];
}

interface ApiResponse {
  health: HealthData | null;
  tips: string[];
}

interface DimensionCard {
  key: "usage_score" | "payment_score" | "engagement_score" | "support_score";
  label: string;
  description: string;
  icon: React.ReactNode;
  iconColor: string;
}

const DIMENSIONS: DimensionCard[] = [
  {
    key: "usage_score",
    label: "Platform usage",
    description: "How actively you use the automation platform and its features.",
    icon: <Activity className="size-4" />,
    iconColor: "var(--accent-purple)",
  },
  {
    key: "payment_score",
    label: "Account standing",
    description: "Your subscription and payment status with AnyVision Media.",
    icon: <CreditCard className="size-4" />,
    iconColor: "var(--accent-teal)",
  },
  {
    key: "engagement_score",
    label: "Growth activity",
    description: "Content publishing, lead responses, and growth-related actions.",
    icon: <Megaphone className="size-4" />,
    iconColor: "var(--accent-coral)",
  },
  {
    key: "support_score",
    label: "Support experience",
    description: "Open ticket resolution and your overall support interactions.",
    icon: <LifeBuoy className="size-4" />,
    iconColor: "var(--warning)",
  },
];

/**
 * 7-day vs prior-7-day change for a health dimension, as a percentage.
 *
 * Returns `null` when we can't compare honestly:
 *   - fewer than 2 history entries,
 *   - either window is empty,
 *   - prior-week average is 0 (no baseline — can't scale).
 * The UI renders null as an em-dash rather than a fabricated "0%".
 */
function computeWeeklyTrend(
  history: HealthHistoryEntry[],
  key: keyof HealthHistoryEntry,
): number | null {
  if (history.length < 2) return null;
  const sorted = [...history].sort(
    (a, b) => new Date(a.score_date).getTime() - new Date(b.score_date).getTime(),
  );
  const recent = sorted.slice(-7);
  const prior = sorted.slice(-14, -7);
  if (recent.length === 0 || prior.length === 0) return null;
  const recentAvg = recent.reduce((s, r) => s + (r[key] as number), 0) / recent.length;
  const priorAvg = prior.reduce((s, r) => s + (r[key] as number), 0) / prior.length;
  if (priorAvg === 0) return recentAvg === 0 ? 0 : null;
  const raw = ((recentAvg - priorAvg) / priorAvg) * 100;
  return Math.round(raw * 10) / 10;
}

export default function PortalHealthPage() {
  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchHealth() {
      try {
        const res = await fetch("/api/portal/health");
        if (!res.ok) throw new Error("Failed to load");
        const json: ApiResponse = await res.json();
        setData(json);
      } catch {
        toast.error("Unable to load your health data");
      } finally {
        setLoading(false);
      }
    }
    fetchHealth();
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader
          eyebrow="Business health"
          title="Your health score"
          description="A holistic view of your account across usage, payments, growth, and support."
        />
        <LoadingState variant="dashboard" />
      </div>
    );
  }

  const health = data?.health ?? null;
  const current = health?.current ?? null;
  const history = health?.history ?? [];
  const tips = data?.tips ?? [];

  const trendData = [...history]
    .sort((a, b) => new Date(a.score_date).getTime() - new Date(b.score_date).getTime())
    .slice(-30)
    .map((entry) => ({
      date: new Date(entry.score_date).toLocaleDateString("en-ZA", {
        day: "2-digit",
        month: "short",
      }),
      value: entry.composite_score,
    }));

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Business health"
        title="Your health score"
        description="A holistic view of your account across usage, payments, growth, and support."
        actions={
          current ? (
            <RiskBadge
              level={current.risk_level as "low" | "medium" | "high" | "critical"}
              size="md"
            />
          ) : null
        }
      />

      {current ? (
        <>
          {/* Big gauge */}
          <Card variant="default" accent="gradient-static" padding="lg">
            <div className="flex justify-center py-4">
              <HealthGauge
                score={current.composite_score}
                size="lg"
                label="Overall score"
                showBreakdown
                breakdownScores={{
                  usage: current.usage_score,
                  payment: current.payment_score,
                  engagement: current.engagement_score,
                  support: current.support_score,
                }}
              />
            </div>
          </Card>

          {/* 30-day trend */}
          {trendData.length > 1 ? (
            <TrendChart
              data={trendData}
              title="30-day health trend"
              subtitle="Composite score over time"
              color="teal"
              height={200}
              showGranularity={false}
            />
          ) : null}

          {/* Dimension cards */}
          <section className="grid gap-4 md:grid-cols-2">
            {DIMENSIONS.map((dim) => {
              const score = current[dim.key] ?? 0;
              const weeklyTrend = computeWeeklyTrend(history, dim.key);
              return (
                <Card key={dim.key} variant="default" padding="lg" className="flex flex-col gap-4">
                  <CardHeader className="pb-0">
                    <div className="flex items-center gap-2">
                      <span
                        className="grid place-items-center size-8 rounded-[var(--radius-sm)]"
                        style={{
                          background: `color-mix(in srgb, ${dim.iconColor} 12%, transparent)`,
                          color: dim.iconColor,
                        }}
                      >
                        {dim.icon}
                      </span>
                      <CardTitle className="text-sm">{dim.label}</CardTitle>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-4">
                      <HealthGauge score={score} size="sm" animate={false} />
                      <div className="flex-1 flex flex-col gap-2 min-w-0">
                        <p className="text-xs text-[var(--text-muted)] leading-relaxed">
                          {dim.description}
                        </p>
                        <div className="flex items-center gap-2">
                          <span className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-dim)]">
                            7-day:
                          </span>
                          <ComparisonArrow value={weeklyTrend} size="sm" />
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </section>

          {/* Improvement tips */}
          {tips.length > 0 ? (
            <Card variant="default" accent="gradient" padding="lg">
              <CardHeader>
                <div className="flex items-center gap-2">
                  <span className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--warning)_12%,transparent)] text-[var(--warning)]">
                    <Lightbulb className="size-4" aria-hidden />
                  </span>
                  <CardTitle className="text-base">Improvement tips</CardTitle>
                </div>
                <CardDescription className="mt-2">
                  Quick wins to improve your composite score.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="flex flex-col gap-2">
                  {tips.map((tip, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-[var(--text-muted)] leading-relaxed"
                    >
                      <span
                        aria-hidden
                        className="mt-1.5 size-1.5 shrink-0 rounded-full bg-[var(--accent-purple)]"
                      />
                      {tip}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : (
        <EmptyState
          icon={<HeartPulse className="size-5" />}
          title="No health data yet"
          description="Your business health score will appear here once our system begins tracking your usage, payments, and engagement activity."
        />
      )}
    </div>
  );
}
