"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import {
  HeartPulse,
  ArrowLeft,
  Activity,
  CreditCard,
  Megaphone,
  LifeBuoy,
  Clock,
  CheckCircle2,
  XCircle,
  Mail,
  Phone,
  ClipboardList,
  Gift,
  Users,
  AlertTriangle,
} from "lucide-react";
import { HealthGauge } from "@/components/dashboard/HealthGauge";
import { RiskBadge } from "@/components/ui/RiskBadge";
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
  days_at_risk: number;
  score_details: Record<string, unknown> | null;
}

interface HistoryEntry {
  score_date: string;
  composite_score: number;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
}

interface Alert {
  id: string;
  alert_type: string;
  severity: string;
  message: string;
  resolved_at: string | null;
  created_at: string;
}

interface Intervention {
  id: string;
  intervention_type: string;
  status: string;
  result: string | null;
  notes: string | null;
  assigned_to: string | null;
  created_at: string;
}

interface ClientInfo {
  id: string;
  full_name: string;
  company_name: string | null;
  email: string;
}

interface HealthDetails {
  current: HealthCurrent | null;
  history: HistoryEntry[];
  alerts: Alert[];
}

interface ApiResponse {
  health: HealthDetails | null;
  interventions: Intervention[];
  client: ClientInfo | null;
}

interface DimensionInfo {
  key: "usage_score" | "payment_score" | "engagement_score" | "support_score";
  label: string;
  icon: React.ReactNode;
  detailKey: string;
}

const DIMENSIONS: DimensionInfo[] = [
  {
    key: "usage_score",
    label: "Platform Usage",
    icon: <Activity size={16} className="text-[#6C63FF]" />,
    detailKey: "usage",
  },
  {
    key: "payment_score",
    label: "Account Standing",
    icon: <CreditCard size={16} className="text-[#00D4AA]" />,
    detailKey: "payment",
  },
  {
    key: "engagement_score",
    label: "Growth Activity",
    icon: <Megaphone size={16} className="text-[#F97316]" />,
    detailKey: "engagement",
  },
  {
    key: "support_score",
    label: "Support Experience",
    icon: <LifeBuoy size={16} className="text-[#EAB308]" />,
    detailKey: "support",
  },
];

const INTERVENTION_ICONS: Record<string, React.ReactNode> = {
  email: <Mail size={14} />,
  call: <Phone size={14} />,
  task: <ClipboardList size={14} />,
  offer: <Gift size={14} />,
  meeting: <Users size={14} />,
};

const STATUS_STYLES: Record<string, { icon: React.ReactNode; color: string }> = {
  pending: { icon: <Clock size={14} />, color: "#EAB308" },
  completed: { icon: <CheckCircle2 size={14} />, color: "#10B981" },
  failed: { icon: <XCircle size={14} />, color: "#EF4444" },
  in_progress: { icon: <Clock size={14} />, color: "#6C63FF" },
};

const SEVERITY_COLORS: Record<string, string> = {
  critical: "#EF4444",
  high: "#F97316",
  medium: "#EAB308",
  low: "#10B981",
};

export default function AdminHealthDetailPage() {
  const params = useParams();
  const router = useRouter();
  const clientId = params.clientId as string;

  const [data, setData] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchDetail() {
      try {
        const res = await fetch(`/api/admin/health/${clientId}`);
        if (!res.ok) throw new Error("Failed to load");
        const json: ApiResponse = await res.json();
        setData(json);
      } catch {
        toast.error("Failed to load client health details");
      } finally {
        setLoading(false);
      }
    }
    fetchDetail();
  }, [clientId]);

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-[200px] w-[200px] mx-auto" variant="circle" />
        <div className="grid grid-cols-2 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
        <Skeleton className="h-[200px]" />
      </div>
    );
  }

  const health = data?.health ?? null;
  const current = health?.current ?? null;
  const history = health?.history ?? [];
  const alerts = health?.alerts ?? [];
  const interventions = data?.interventions ?? [];
  const client = data?.client ?? null;

  const trendData = [...history]
    .sort((a, b) => new Date(a.score_date).getTime() - new Date(b.score_date).getTime())
    .map((entry) => ({
      date: new Date(entry.score_date).toLocaleDateString("en-ZA", {
        day: "2-digit",
        month: "short",
      }),
      value: entry.composite_score,
    }));

  const displayName = client?.full_name ?? clientId.slice(0, 8);

  return (
    <div className="space-y-8">
      {/* Back Button */}
      <button
        onClick={() => router.push("/admin/health")}
        className="flex items-center gap-2 text-sm text-[#6B7280] hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Health Dashboard
      </button>

      {/* Hero */}
      <div className="flex flex-col md:flex-row items-center gap-6">
        <div className="flex-1 space-y-2">
          <h1 className="text-2xl font-bold text-white">{displayName}</h1>
          {client?.company_name && (
            <p className="text-sm text-[#6B7280]">{client.company_name}</p>
          )}
          {client?.email && (
            <p className="text-xs text-[#6B7280]">{client.email}</p>
          )}
          {current && (
            <div className="flex items-center gap-3 pt-2">
              <RiskBadge
                level={current.risk_level as "low" | "medium" | "high" | "critical"}
              />
              {current.days_at_risk > 0 && (
                <span className="text-xs text-[#EF4444]">
                  {current.days_at_risk} days at risk
                </span>
              )}
            </div>
          )}
        </div>
        <div className="shrink-0">
          {current ? (
            <HealthGauge
              score={current.composite_score}
              size="lg"
              label="Overall"
              showBreakdown
              breakdownScores={{
                usage: current.usage_score,
                payment: current.payment_score,
                engagement: current.engagement_score,
                support: current.support_score,
              }}
            />
          ) : (
            <div className="w-[200px] h-[200px] flex items-center justify-center">
              <HeartPulse size={56} className="text-[#6B7280]" />
            </div>
          )}
        </div>
      </div>

      {current && (
        <>
          {/* Dimension Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {DIMENSIONS.map((dim) => {
              const score = current[dim.key] ?? 0;
              const detail = current.score_details?.[dim.detailKey];
              return (
                <div key={dim.key} className="glass-card p-4 space-y-2">
                  <div className="flex items-center gap-2">
                    {dim.icon}
                    <span className="text-xs font-medium text-[#B0B8C8]">
                      {dim.label}
                    </span>
                  </div>
                  <HealthGauge score={score} size="sm" />
                  {typeof detail === "string" ? (
                    <p className="text-[10px] text-[#6B7280]">{detail}</p>
                  ) : null}
                </div>
              );
            })}
          </div>

          {/* 90-day Trend Chart */}
          {trendData.length > 1 && (
            <TrendChart
              data={trendData}
              title="90-Day Health Trend"
              subtitle={`${displayName}'s composite score over time`}
              color="purple"
              height={200}
              showGranularity={false}
            />
          )}
        </>
      )}

      {/* Intervention Timeline */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <ClipboardList size={18} className="text-[#6C63FF]" />
          Intervention History
        </h2>
        {interventions.length > 0 ? (
          <div className="glass-card divide-y divide-[rgba(255,255,255,0.06)]">
            {interventions.map((iv) => {
              const statusStyle = STATUS_STYLES[iv.status] ?? STATUS_STYLES.pending;
              return (
                <div key={iv.id} className="p-4 flex items-start gap-4">
                  <div
                    className="w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                    style={{
                      background: `${statusStyle.color}15`,
                      color: statusStyle.color,
                    }}
                  >
                    {INTERVENTION_ICONS[iv.intervention_type] ?? (
                      <ClipboardList size={14} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-white capitalize">
                        {iv.intervention_type}
                      </span>
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
                        style={{
                          background: `${statusStyle.color}15`,
                          color: statusStyle.color,
                        }}
                      >
                        {statusStyle.icon}
                        {iv.status}
                      </span>
                    </div>
                    {iv.notes && (
                      <p className="text-xs text-[#6B7280]">{iv.notes}</p>
                    )}
                    {iv.result && (
                      <p className="text-xs text-[#B0B8C8]">
                        Result: {iv.result}
                      </p>
                    )}
                  </div>
                  <span className="text-[11px] text-[#6B7280] shrink-0">
                    {new Date(iv.created_at).toLocaleDateString("en-ZA", {
                      day: "2-digit",
                      month: "short",
                      year: "numeric",
                    })}
                  </span>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="glass-card p-8 text-center">
            <ClipboardList size={36} className="mx-auto text-[#6B7280] mb-2" />
            <p className="text-sm text-[#6B7280]">No interventions recorded yet</p>
          </div>
        )}
      </div>

      {/* Alert History */}
      <div className="space-y-3">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <AlertTriangle size={18} className="text-[#F97316]" />
          Alert History
        </h2>
        {alerts.length > 0 ? (
          <div className="glass-card divide-y divide-[rgba(255,255,255,0.06)]">
            {alerts.map((alert) => {
              const sevColor = SEVERITY_COLORS[alert.severity] ?? "#6B7280";
              const isResolved = !!alert.resolved_at;
              return (
                <div key={alert.id} className="p-4 flex items-start gap-4">
                  <div
                    className="w-2 h-2 rounded-full mt-1.5 shrink-0"
                    style={{ background: sevColor }}
                  />
                  <div className="flex-1 min-w-0 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-white">{alert.message}</span>
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-medium"
                        style={{
                          background: `${sevColor}15`,
                          color: sevColor,
                        }}
                      >
                        {alert.severity}
                      </span>
                    </div>
                    <p className="text-xs text-[#6B7280]">
                      Type: {alert.alert_type}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className="text-[11px] text-[#6B7280]">
                      {new Date(alert.created_at).toLocaleDateString("en-ZA", {
                        day: "2-digit",
                        month: "short",
                      })}
                    </span>
                    {isResolved ? (
                      <span className="inline-flex items-center gap-1 text-[10px] text-[#10B981]">
                        <CheckCircle2 size={10} /> Resolved
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[10px] text-[#F97316]">
                        <Clock size={10} /> Open
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="glass-card p-8 text-center">
            <AlertTriangle size={36} className="mx-auto text-[#6B7280] mb-2" />
            <p className="text-sm text-[#6B7280]">No alerts recorded</p>
          </div>
        )}
      </div>
    </div>
  );
}
