"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import Link from "next/link";
import {
  Bot,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Wrench,
  Shield,
} from "lucide-react";

interface AgentStatus {
  id: string;
  agent_id: string;
  agent_name: string;
  department: string;
  status: "active" | "degraded" | "down" | "inactive";
  health_score: number;
  workflows_monitored: number;
  workflow_ids: string[];
  last_heartbeat: string;
  kpi_summary: Record<string, number>;
  error_summary: Array<{ workflow_id: string; errors: number }>;
  error_count: number;
  tier: number;
  updated_at: string;
}

interface OrchestratorAlert {
  id: number;
  agent_id: string;
  severity: "P1" | "P2" | "P3" | "P4";
  category: string;
  title: string;
  description: string;
  recommended_action: string;
  status: "open" | "acknowledged" | "resolved" | "dismissed";
  created_at: string;
  resolved_at: string | null;
}

const statusConfig = {
  active: { color: "bg-emerald-500", label: "Active", icon: CheckCircle },
  degraded: { color: "bg-yellow-500", label: "Degraded", icon: AlertTriangle },
  down: { color: "bg-red-500", label: "Down", icon: XCircle },
  inactive: { color: "bg-gray-500", label: "Inactive", icon: Wrench },
};

const severityConfig = {
  P1: { color: "text-red-400 bg-red-500/10", label: "Critical" },
  P2: { color: "text-orange-400 bg-orange-500/10", label: "High" },
  P3: { color: "text-yellow-400 bg-yellow-500/10", label: "Medium" },
  P4: { color: "text-blue-400 bg-blue-500/10", label: "Low" },
};

function HealthGauge({ score }: { score: number }) {
  const radius = 40;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : score >= 30 ? "#f97316" : "#ef4444";

  return (
    <div className="relative w-24 h-24">
      <svg className="w-24 h-24 -rotate-90" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="8" />
        <circle
          cx="50"
          cy="50"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="8"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-xl font-bold text-white">{score}</span>
        <span className="text-[10px] text-[#6B7280]">health</span>
      </div>
    </div>
  );
}

const TIER_LABELS: Record<number, string> = {
  1: "Executive",
  2: "Revenue & Growth",
  3: "Client-Facing",
  4: "Infrastructure",
  5: "Intelligence",
  6: "Quality & Governance",
  7: "Specialist",
};

const DEPT_ORDER = [
  "Executive", "Orchestrator", "Finance", "Marketing", "Sales",
  "Client Relations", "Support", "WhatsApp", "DevOps", "Engineering",
  "Content", "Intelligence", "Quality", "Governance", "Operations",
];

export default function AgentsDashboard() {
  const [agents, setAgents] = useState<AgentStatus[]>([]);
  const [alerts, setAlerts] = useState<OrchestratorAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterDept, setFilterDept] = useState<string>("all");

  useEffect(() => {
    async function fetchData() {
      try {
        const [agentsRes, alertsRes] = await Promise.all([
          fetch("/api/admin/agents"),
          fetch("/api/admin/agents/alerts"),
        ]);

        if (agentsRes.ok) {
          setAgents(await agentsRes.json());
        }
        if (alertsRes.ok) {
          setAlerts(await alertsRes.json());
        }
      } catch (err) {
        toast.error("Failed to load agent data");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  const activeCount = agents.filter((a) => a.status === "active").length;
  const degradedCount = agents.filter((a) => a.status === "degraded").length;
  const downCount = agents.filter((a) => a.status === "down").length;
  const inactiveCount = agents.filter((a) => a.status === "inactive").length;
  const openAlerts = alerts.filter((a) => a.status === "open").length;
  const totalWorkflows = agents.reduce((sum, a) => sum + a.workflows_monitored, 0);
  const avgHealth =
    agents.length > 0
      ? Math.round(agents.filter((a) => a.status !== "inactive").reduce((sum, a) => sum + a.health_score, 0) / Math.max(agents.filter((a) => a.status !== "inactive").length, 1))
      : 0;

  // Group agents by department
  const departments = [...new Set(agents.map((a) => a.department))].sort(
    (a, b) => (DEPT_ORDER.indexOf(a) === -1 ? 99 : DEPT_ORDER.indexOf(a)) - (DEPT_ORDER.indexOf(b) === -1 ? 99 : DEPT_ORDER.indexOf(b))
  );
  const filteredAgents = filterDept === "all" ? agents : agents.filter((a) => a.department === filterDept);

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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <Bot className="text-[#6C63FF]" size={28} />
            AI Agent Operations
          </h1>
          <p className="text-[#6B7280] mt-1">
            Real-time health monitoring across all autonomous agents
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${downCount > 0 ? "bg-red-500 animate-pulse" : "bg-emerald-500"}`} />
          <span className="text-sm text-[#6B7280]">
            {downCount > 0 ? `${downCount} agent(s) down` : "All systems operational"}
          </span>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-white">{agents.length}</div>
          <div className="text-xs text-[#6B7280] mt-1">Total Agents</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-emerald-400">{activeCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">Active</div>
        </Card>
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${degradedCount > 0 ? "text-yellow-400" : "text-[#6B7280]"}`}>{degradedCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">Degraded</div>
        </Card>
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${inactiveCount > 0 ? "text-gray-400" : "text-[#6B7280]"}`}>{inactiveCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">Inactive</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-[#FF6D5A]">{totalWorkflows}</div>
          <div className="text-xs text-[#6B7280] mt-1">Workflows</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-[#6C63FF]">{avgHealth}%</div>
          <div className="text-xs text-[#6B7280] mt-1">Avg Health</div>
        </Card>
      </div>

      {/* Department Filter */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => setFilterDept("all")}
          className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
            filterDept === "all" ? "bg-[#6C63FF] text-white" : "bg-[rgba(255,255,255,0.06)] text-[#6B7280] hover:text-white"
          }`}
        >
          All ({agents.length})
        </button>
        {departments.map((dept) => {
          const count = agents.filter((a) => a.department === dept).length;
          return (
            <button
              key={dept}
              onClick={() => setFilterDept(dept)}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                filterDept === dept ? "bg-[#6C63FF] text-white" : "bg-[rgba(255,255,255,0.06)] text-[#6B7280] hover:text-white"
              }`}
            >
              {dept} ({count})
            </button>
          );
        })}
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {filteredAgents.map((agent) => {
          const config = statusConfig[agent.status];
          const tierLabel = TIER_LABELS[agent.tier] || "Other";
          return (
            <Link key={agent.agent_id} href={`/admin/agents/${agent.agent_id}`} className="block">
            <Card className={`p-5 hover:border-[rgba(108,99,255,0.3)] transition-colors cursor-pointer ${agent.status === "inactive" ? "opacity-60" : ""}`}>
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <div className={`w-2.5 h-2.5 rounded-full ${config.color}`} />
                    <h3 className="text-sm font-semibold text-white">{agent.agent_name}</h3>
                  </div>
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-xs text-[#6B7280]">{agent.department}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-[rgba(108,99,255,0.15)] text-[#6C63FF]">
                      T{agent.tier} {tierLabel}
                    </span>
                  </div>

                  <div className="space-y-2">
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[#6B7280]">Status</span>
                      <Badge variant={agent.status === "active" ? "success" : agent.status === "degraded" ? "warning" : agent.status === "inactive" ? "default" : "danger"}>
                        {config.label}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[#6B7280]">Workflows</span>
                      <span className="text-white">{agent.workflows_monitored}</span>
                    </div>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-[#6B7280]">Last Heartbeat</span>
                      <span className="text-white">
                        {agent.last_heartbeat
                          ? formatDistanceToNow(new Date(agent.last_heartbeat), { addSuffix: true })
                          : "Never"}
                      </span>
                    </div>
                  </div>
                </div>
                <HealthGauge score={agent.health_score} />
              </div>

              {/* Error summary */}
              {agent.error_count > 0 && (
                <div className="mt-3 pt-3 border-t border-[rgba(255,255,255,0.06)]">
                  <p className="text-xs text-red-400 flex items-center gap-1">
                    <AlertTriangle size={12} />
                    {agent.error_count} error(s) detected
                  </p>
                </div>
              )}
            </Card>
            </Link>
          );
        })}
      </div>

      {/* Open Alerts */}
      {alerts.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center gap-2">
            <Shield size={20} className="text-red-400" />
            Recent Alerts
          </h2>
          <Card className="divide-y divide-[rgba(255,255,255,0.06)]">
            {alerts.slice(0, 10).map((alert) => {
              const sev = severityConfig[alert.severity];
              return (
                <div key={alert.id} className="p-4 flex items-start gap-3">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${sev.color}`}>
                    {alert.severity}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-white font-medium">{alert.title}</p>
                    <p className="text-xs text-[#6B7280] mt-0.5 truncate">{alert.description}</p>
                    {alert.recommended_action && (
                      <p className="text-xs text-[#6C63FF] mt-1">Recommended: {alert.recommended_action}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <Badge variant={alert.status === "open" ? "danger" : alert.status === "acknowledged" ? "warning" : "success"}>
                      {alert.status}
                    </Badge>
                    <p className="text-[10px] text-[#6B7280] mt-1">
                      {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                    </p>
                  </div>
                </div>
              );
            })}
          </Card>
        </div>
      )}

      {agents.length === 0 && (
        <EmptyState
          icon={<Bot size={48} />}
          title="No agents registered"
          description="Run the Supabase migration and seed the agent_status table to see your AI agents here."
        />
      )}
    </div>
  );
}
