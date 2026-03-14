"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  HeartPulse,
  TrendingDown,
  TrendingUp,
  AlertTriangle,
  Calendar,
  Users,
} from "lucide-react";

interface ClientHealth {
  id: string;
  client_id: string;
  score_date: string;
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
  composite_score: number;
  risk_level: string;
}

interface RenewalEntry {
  id: string;
  client_id: string;
  current_plan: string;
  monthly_value: number;
  renewal_date: string;
  days_until_renewal: number;
  health_score: number;
  risk_level: string;
  status: string;
  last_contact_date: string;
  next_action: string;
}

interface ClientInfo {
  id: string;
  company_name: string;
  email: string;
}

const riskColors: Record<string, string> = {
  low: "text-emerald-400",
  medium: "text-yellow-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

const riskBadgeVariant = (risk: string) => {
  if (risk === "low") return "success" as const;
  if (risk === "medium") return "warning" as const;
  return "danger" as const;
};

const statusColors: Record<string, string> = {
  upcoming: "text-blue-400 bg-blue-500/10",
  in_progress: "text-yellow-400 bg-yellow-500/10",
  renewed: "text-emerald-400 bg-emerald-500/10",
  churned: "text-red-400 bg-red-500/10",
  downgraded: "text-orange-400 bg-orange-500/10",
};

export default function HealthDashboard() {
  const [healthScores, setHealthScores] = useState<ClientHealth[]>([]);
  const [renewals, setRenewals] = useState<RenewalEntry[]>([]);
  const [clients, setClients] = useState<ClientInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch("/api/admin/health");
        if (res.ok) {
          const data = await res.json();
          setHealthScores(data.healthScores || []);
          setRenewals(data.renewals || []);
          setClients(data.clients || []);
        }
      } catch {
        toast.error("Failed to load health data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const getClientName = (clientId: string) => {
    const client = clients.find((c) => c.id === clientId);
    return client?.company_name || client?.email || clientId.slice(0, 8);
  };

  const atRiskCount = healthScores.filter((h) => h.composite_score < 40).length;
  const healthyCount = healthScores.filter((h) => h.composite_score >= 70).length;
  const avgScore = healthScores.length > 0
    ? Math.round(healthScores.reduce((sum, h) => sum + h.composite_score, 0) / healthScores.length)
    : 0;
  const upcomingRenewals = renewals.filter((r) => r.status === "upcoming" && r.days_until_renewal <= 30).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#6C63FF]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <HeartPulse className="text-[#FF6D5A]" size={28} />
          Client Health & Renewals
        </h1>
        <p className="text-[#6B7280] mt-1">
          Monitor client health scores, churn risk, and upcoming renewals
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-white">{healthScores.length}</div>
          <div className="text-xs text-[#6B7280] mt-1">Tracked Clients</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-emerald-400">{healthyCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">Healthy (70+)</div>
        </Card>
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${atRiskCount > 0 ? "text-red-400 animate-pulse" : "text-[#6B7280]"}`}>{atRiskCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">At Risk (&lt;40)</div>
        </Card>
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${upcomingRenewals > 0 ? "text-[#FF6D5A]" : "text-[#6B7280]"}`}>{upcomingRenewals}</div>
          <div className="text-xs text-[#6B7280] mt-1">Renewals (30d)</div>
        </Card>
      </div>

      {/* Health Scores Table */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Users size={20} className="text-[#6C63FF]" />
          Client Health Scores
        </h2>
        {healthScores.length > 0 ? (
          <Card className="overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)]">
                  <th className="text-left p-3 text-[#6B7280] font-medium">Client</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Usage</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Payment</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Engagement</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Support</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Overall</th>
                  <th className="text-center p-3 text-[#6B7280] font-medium">Risk</th>
                </tr>
              </thead>
              <tbody>
                {healthScores.sort((a, b) => a.composite_score - b.composite_score).map((h) => (
                  <tr key={h.id} className="border-b border-[rgba(255,255,255,0.03)] hover:bg-[rgba(255,255,255,0.02)]">
                    <td className="p-3 text-white font-medium">{getClientName(h.client_id)}</td>
                    <td className="p-3 text-center text-white">{h.usage_score}</td>
                    <td className="p-3 text-center text-white">{h.payment_score}</td>
                    <td className="p-3 text-center text-white">{h.engagement_score}</td>
                    <td className="p-3 text-center text-white">{h.support_score}</td>
                    <td className="p-3 text-center">
                      <span className={`font-bold ${h.composite_score >= 70 ? "text-emerald-400" : h.composite_score >= 40 ? "text-yellow-400" : "text-red-400"}`}>
                        {h.composite_score}
                      </span>
                    </td>
                    <td className="p-3 text-center">
                      <Badge variant={riskBadgeVariant(h.risk_level)}>
                        {h.risk_level}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : (
          <Card className="p-8 text-center">
            <HeartPulse size={48} className="mx-auto text-[#6B7280] mb-3" />
            <p className="text-white font-medium">No health data yet</p>
            <p className="text-sm text-[#6B7280]">Client health scores will populate once the Client Relations agent starts running.</p>
          </Card>
        )}
      </div>

      {/* Renewal Pipeline */}
      <div>
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
          <Calendar size={20} className="text-[#FF6D5A]" />
          Renewal Pipeline
        </h2>
        {renewals.length > 0 ? (
          <Card className="divide-y divide-[rgba(255,255,255,0.06)]">
            {renewals.sort((a, b) => a.days_until_renewal - b.days_until_renewal).map((r) => (
              <div key={r.id} className="p-4 flex items-center gap-4">
                <div className="flex-1">
                  <p className="text-sm text-white font-medium">{getClientName(r.client_id)}</p>
                  <p className="text-xs text-[#6B7280]">{r.current_plan} - R{r.monthly_value?.toLocaleString()}/mo</p>
                </div>
                <div className="text-center">
                  <p className={`text-lg font-bold ${r.days_until_renewal <= 14 ? "text-red-400" : r.days_until_renewal <= 30 ? "text-yellow-400" : "text-white"}`}>
                    {r.days_until_renewal}d
                  </p>
                  <p className="text-[10px] text-[#6B7280]">until renewal</p>
                </div>
                <div className="text-center min-w-[60px]">
                  <span className={`text-xs font-medium ${riskColors[r.risk_level] || "text-[#6B7280]"}`}>
                    {r.health_score}
                  </span>
                  <p className="text-[10px] text-[#6B7280]">health</p>
                </div>
                <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[r.status] || "text-[#6B7280] bg-[rgba(255,255,255,0.06)]"}`}>
                  {r.status}
                </span>
              </div>
            ))}
          </Card>
        ) : (
          <Card className="p-8 text-center">
            <Calendar size={48} className="mx-auto text-[#6B7280] mb-3" />
            <p className="text-white font-medium">No renewals tracked yet</p>
            <p className="text-sm text-[#6B7280]">Renewal data will appear once clients are onboarded with subscription plans.</p>
          </Card>
        )}
      </div>
    </div>
  );
}
