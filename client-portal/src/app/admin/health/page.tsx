"use client";

import { useEffect, useState, useMemo } from "react";
import { useRouter } from "next/navigation";
import {
  HeartPulse,
  Users,
  ShieldCheck,
  AlertTriangle,
  AlertOctagon,
  Filter,
  Clock,
  Mail,
  Phone,
  ClipboardList,
} from "lucide-react";
import { StatCard } from "@/components/charts/StatCard";
import { ClientHealthCard } from "@/components/dashboard/ClientHealthCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { RiskBadge } from "@/components/ui/RiskBadge";
import { toast } from "sonner";
import { createClient } from "@/lib/supabase/client";

interface ClientHealthRow {
  id: string;
  client_id: string;
  score_date: string;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
  composite_score: number;
  risk_level: string;
  trend: string;
  days_at_risk: number;
}

interface ClientInfo {
  id: string;
  full_name: string;
  company_name: string | null;
}

interface Intervention {
  id: string;
  client_id: string;
  intervention_type: string;
  status: string;
  notes: string | null;
  created_at: string;
  health_alert_id: string | null;
}

type RiskFilter = "all" | "critical" | "high" | "medium" | "low";

const INTERVENTION_ICONS: Record<string, React.ReactNode> = {
  email: <Mail size={14} />,
  call: <Phone size={14} />,
  task: <ClipboardList size={14} />,
  offer: <ShieldCheck size={14} />,
  meeting: <Users size={14} />,
};

export default function AdminHealthDashboard() {
  const router = useRouter();
  const [healthScores, setHealthScores] = useState<ClientHealthRow[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [interventions, setInterventions] = useState<Intervention[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<RiskFilter>("all");

  useEffect(() => {
    async function fetchData() {
      try {
        const supabase = createClient();

        const [scoresRes, clientsRes, interventionsRes] = await Promise.all([
          supabase
            .from("client_health_scores")
            .select("*")
            .order("composite_score", { ascending: true }),
          supabase
            .from("clients")
            .select("id, full_name, company_name"),
          supabase
            .from("health_interventions")
            .select("*")
            .eq("status", "pending")
            .order("created_at", { ascending: false })
            .limit(20),
        ]);

        setHealthScores(scoresRes.data ?? []);
        setClients(clientsRes.data ?? []);
        setInterventions(interventionsRes.data ?? []);
      } catch {
        toast.error("Failed to load health dashboard");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const clientMap = useMemo(() => {
    const map = new Map<string, ClientInfo>();
    for (const c of clients) {
      map.set(c.id, c);
    }
    return map;
  }, [clients]);

  const latestPerClient = useMemo(() => {
    const byClient = new Map<string, ClientHealthRow>();
    for (const score of healthScores) {
      const existing = byClient.get(score.client_id);
      if (!existing || new Date(score.score_date) > new Date(existing.score_date)) {
        byClient.set(score.client_id, score);
      }
    }
    return Array.from(byClient.values());
  }, [healthScores]);

  const stats = useMemo(() => {
    const total = latestPerClient.length;
    const healthy = latestPerClient.filter((h) => h.composite_score > 70).length;
    const atRisk = latestPerClient.filter(
      (h) => h.composite_score >= 30 && h.composite_score <= 70
    ).length;
    const critical = latestPerClient.filter((h) => h.composite_score < 30).length;
    return { total, healthy, atRisk, critical };
  }, [latestPerClient]);

  const filteredClients = useMemo(() => {
    const sorted = [...latestPerClient].sort(
      (a, b) => a.composite_score - b.composite_score
    );
    if (filter === "all") return sorted;
    if (filter === "critical") return sorted.filter((h) => h.composite_score < 30);
    if (filter === "high")
      return sorted.filter((h) => h.composite_score >= 30 && h.composite_score < 50);
    if (filter === "medium")
      return sorted.filter((h) => h.composite_score >= 50 && h.composite_score <= 70);
    return sorted.filter((h) => h.composite_score > 70);
  }, [latestPerClient, filter]);

  const clientCards = useMemo(() => {
    return filteredClients.map((h) => {
      const info = clientMap.get(h.client_id);
      return {
        id: h.client_id,
        full_name: info?.full_name ?? h.client_id.slice(0, 8),
        company_name: info?.company_name ?? null,
        composite_score: h.composite_score,
        usage_score: h.usage_score,
        payment_score: h.payment_score,
        engagement_score: h.engagement_score,
        support_score: h.support_score,
        risk_level: h.risk_level,
        trend: h.trend,
        days_at_risk: h.days_at_risk,
      };
    });
  }, [filteredClients, clientMap]);

  function handleAction(clientId: string, action: string) {
    if (action === "view") {
      router.push(`/admin/health/${clientId}`);
    } else if (action === "checkin") {
      toast.info("Check-in scheduled (coming soon)");
    } else if (action === "task") {
      toast.info("Task created (coming soon)");
    }
  }

  const filters: { label: string; value: RiskFilter }[] = [
    { label: "All", value: "all" },
    { label: "Critical", value: "critical" },
    { label: "High Risk", value: "high" },
    { label: "Medium", value: "medium" },
    { label: "Healthy", value: "low" },
  ];

  if (loading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-64" />
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-64" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <HeartPulse className="text-[#FF6D5A]" size={28} />
          Client Health Dashboard
        </h1>
        <p className="text-[#6B7280] mt-1">
          Monitor client health, identify churn risk, and manage interventions
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Total Tracked"
          value={stats.total}
          icon={<Users size={22} />}
          color="purple"
        />
        <StatCard
          title="Healthy (70+)"
          value={stats.healthy}
          icon={<ShieldCheck size={22} />}
          color="teal"
        />
        <StatCard
          title="At Risk (30-70)"
          value={stats.atRisk}
          icon={<AlertTriangle size={22} />}
          color="amber"
        />
        <StatCard
          title="Critical (<30)"
          value={stats.critical}
          icon={<AlertOctagon size={22} />}
          color="red"
        />
      </div>

      {/* Filter Pills */}
      <div className="flex items-center gap-2 flex-wrap">
        <Filter size={14} className="text-[#6B7280]" />
        {filters.map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
              filter === f.value
                ? "bg-[rgba(108,99,255,0.15)] text-[#6C63FF]"
                : "bg-[rgba(255,255,255,0.04)] text-[#6B7280] hover:text-white hover:bg-[rgba(255,255,255,0.08)]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Client Health Grid */}
      {clientCards.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {clientCards.map((client) => (
            <ClientHealthCard
              key={client.id}
              client={client}
              onAction={handleAction}
            />
          ))}
        </div>
      ) : (
        <div className="glass-card p-12 text-center space-y-3">
          <HeartPulse size={48} className="mx-auto text-[#6B7280]" />
          <p className="text-white font-medium">
            {filter === "all"
              ? "No health data yet"
              : `No clients matching "${filter}" filter`}
          </p>
          <p className="text-sm text-[#6B7280]">
            {filter === "all"
              ? "Client health scores will populate once the health scorer runs."
              : "Try a different filter to see other clients."}
          </p>
        </div>
      )}

      {/* Intervention Queue */}
      {interventions.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Clock size={18} className="text-[#F97316]" />
            Pending Interventions
          </h2>
          <div className="glass-card divide-y divide-[rgba(255,255,255,0.06)]">
            {interventions.map((iv) => {
              const info = clientMap.get(iv.client_id);
              return (
                <div
                  key={iv.id}
                  className="p-4 flex items-center gap-4 hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer"
                  onClick={() => router.push(`/admin/health/${iv.client_id}`)}
                >
                  <div className="w-8 h-8 rounded-lg bg-[rgba(249,115,22,0.1)] text-[#F97316] flex items-center justify-center shrink-0">
                    {INTERVENTION_ICONS[iv.intervention_type] ?? (
                      <ClipboardList size={14} />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium truncate">
                      {info?.full_name ?? iv.client_id.slice(0, 8)}
                    </p>
                    <p className="text-xs text-[#6B7280] truncate">
                      {iv.intervention_type} &middot;{" "}
                      {iv.notes ?? "No notes"}
                    </p>
                  </div>
                  <RiskBadge level="high" size="sm" pulse={false} />
                  <span className="text-[11px] text-[#6B7280] shrink-0">
                    {new Date(iv.created_at).toLocaleDateString("en-ZA", {
                      day: "2-digit",
                      month: "short",
                    })}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
