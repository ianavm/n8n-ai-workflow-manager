"use client";

import { useEffect, useState } from "react";
import { HeartPulse, Activity, CreditCard, Megaphone, LifeBuoy, Lightbulb } from "lucide-react";
import { HealthGauge } from "@/components/dashboard/HealthGauge";
import { ComparisonArrow } from "@/components/dashboard/ComparisonArrow";
import { TrendChart } from "@/components/charts/TrendChart";
import { Skeleton } from "@/components/ui/Skeleton";
import { toast } from "sonner";

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
}

const DIMENSIONS: DimensionCard[] = [
  {
    key: "usage_score",
    label: "Platform Usage",
    description: "How actively you use the automation platform and its features",
    icon: <Activity size={16} className="text-[#6C63FF]" />,
  },
  {
    key: "payment_score",
    label: "Account Standing",
    description: "Your subscription and payment status with AnyVision Media",
    icon: <CreditCard size={16} className="text-[#00D4AA]" />,
  },
  {
    key: "engagement_score",
    label: "Growth Activity",
    description: "Content publishing, lead responses, and growth-related actions",
    icon: <Megaphone size={16} className="text-[#F97316]" />,
  },
  {
    key: "support_score",
    label: "Support Experience",
    description: "Open ticket resolution and your overall support interactions",
    icon: <LifeBuoy size={16} className="text-[#EAB308]" />,
  },
];

function computeWeeklyTrend(history: HealthHistoryEntry[], key: keyof HealthHistoryEntry): number {
  if (history.length < 2) return 0;
  const sorted = [...history].sort(
    (a, b) => new Date(a.score_date).getTime() - new Date(b.score_date).getTime()
  );
  const recent = sorted.slice(-7);
  const prior = sorted.slice(-14, -7);
  if (recent.length === 0 || prior.length === 0) return 0;
  const recentAvg = recent.reduce((s, r) => s + (r[key] as number), 0) / recent.length;
  const priorAvg = prior.reduce((s, r) => s + (r[key] as number), 0) / prior.length;
  if (priorAvg === 0) return 0;
  return ((recentAvg - priorAvg) / priorAvg) * 100;
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
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <Skeleton className="w-7 h-7" variant="circle" />
          <Skeleton className="h-7 w-52" />
        </div>
        <div className="flex justify-center">
          <Skeleton className="w-[200px] h-[200px]" variant="circle" />
        </div>
        <Skeleton className="h-[200px] w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-36" />
          ))}
        </div>
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
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <HeartPulse className="text-[#FF6D5A]" size={28} />
          Your Business Health
        </h1>
        <p className="text-[#6B7280] mt-1">
          A holistic view of your account across usage, payments, growth, and support
        </p>
      </div>

      {current ? (
        <>
          {/* Large Gauge */}
          <div className="flex justify-center py-4">
            <HealthGauge
              score={current.composite_score}
              size="lg"
              label="Overall Score"
              showBreakdown
              breakdownScores={{
                usage: current.usage_score,
                payment: current.payment_score,
                engagement: current.engagement_score,
                support: current.support_score,
              }}
            />
          </div>

          {/* 30-day Trend */}
          {trendData.length > 1 && (
            <TrendChart
              data={trendData}
              title="30-Day Health Trend"
              subtitle="Your composite score over time"
              color="teal"
              height={180}
              showGranularity={false}
            />
          )}

          {/* Dimension Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {DIMENSIONS.map((dim) => {
              const score = current[dim.key] ?? 0;
              const weeklyTrend = computeWeeklyTrend(history, dim.key);
              return (
                <div key={dim.key} className="glass-card p-5 space-y-3">
                  <div className="flex items-center gap-2">
                    {dim.icon}
                    <span className="text-sm font-semibold text-white">{dim.label}</span>
                  </div>
                  <div className="flex items-center gap-4">
                    <HealthGauge score={score} size="sm" />
                    <div className="flex-1 space-y-1">
                      <p className="text-xs text-[#6B7280]">{dim.description}</p>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-[#6B7280]">7-day:</span>
                        <ComparisonArrow value={weeklyTrend} size="sm" />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Improvement Tips */}
          {tips.length > 0 && (
            <div
              className="glass-card p-5 space-y-3"
              style={{
                borderImage: "linear-gradient(135deg, rgba(108,99,255,0.4), rgba(0,212,170,0.4)) 1",
                borderWidth: "1px",
                borderStyle: "solid",
              }}
            >
              <div className="flex items-center gap-2">
                <Lightbulb size={16} className="text-[#EAB308]" />
                <span className="text-sm font-semibold text-white">Improvement Tips</span>
              </div>
              <ul className="space-y-2">
                {tips.map((tip, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-[#B0B8C8]"
                  >
                    <span className="text-[#6C63FF] mt-0.5 shrink-0">&#x2022;</span>
                    {tip}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      ) : (
        <div className="glass-card p-12 text-center space-y-3">
          <HeartPulse size={56} className="mx-auto text-[#6B7280]" />
          <p className="text-white font-medium text-lg">No health data yet</p>
          <p className="text-sm text-[#6B7280] max-w-md mx-auto">
            Your business health score will appear here once our system begins tracking
            your usage, payments, and engagement activity.
          </p>
        </div>
      )}
    </div>
  );
}
