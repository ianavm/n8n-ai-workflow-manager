"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  Bot,
  ArrowLeft,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Wrench,
  Activity,
  Workflow,
} from "lucide-react";

interface AgentDetail {
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

const statusConfig = {
  active: { color: "bg-emerald-500", label: "Active", icon: CheckCircle },
  degraded: { color: "bg-yellow-500", label: "Degraded", icon: AlertTriangle },
  down: { color: "bg-red-500", label: "Down", icon: XCircle },
  inactive: { color: "bg-gray-500", label: "Inactive", icon: Wrench },
};

const TIER_LABELS: Record<number, string> = {
  1: "Executive",
  2: "Revenue & Growth",
  3: "Client-Facing",
  4: "Infrastructure",
  5: "Intelligence",
  6: "Quality & Governance",
  7: "Specialist",
};

function HealthGaugeLarge({ score }: { score: number }) {
  const radius = 60;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const color =
    score >= 80 ? "#22c55e" : score >= 60 ? "#eab308" : score >= 30 ? "#f97316" : "#ef4444";

  return (
    <div className="relative w-36 h-36">
      <svg className="w-36 h-36 -rotate-90" viewBox="0 0 140 140">
        <circle cx="70" cy="70" r={radius} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="10" />
        <circle
          cx="70"
          cy="70"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className="transition-all duration-1000 ease-out"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-3xl font-bold text-white">{score}</span>
        <span className="text-xs text-[var(--text-dim)]">health score</span>
      </div>
    </div>
  );
}

export default function AgentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const agentId = params.id as string;
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchAgent() {
      try {
        const res = await fetch("/api/admin/agents");
        if (res.ok) {
          const agents: AgentDetail[] = await res.json();
          const found = agents.find((a) => a.agent_id === agentId);
          setAgent(found || null);
        }
      } catch {
        toast.error("Failed to load agent data");
      } finally {
        setLoading(false);
      }
    }
    fetchAgent();
    const interval = setInterval(fetchAgent, 30000);
    return () => clearInterval(interval);
  }, [agentId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#6C63FF]" />
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="space-y-4">
        <button onClick={() => router.push("/admin/agents")} className="text-[#6C63FF] text-sm flex items-center gap-1 hover:underline">
          <ArrowLeft size={14} /> Back to Agents
        </button>
        <Card className="p-8 text-center">
          <Bot size={48} className="mx-auto text-[var(--text-dim)] mb-3" />
          <p className="text-white font-medium">Agent not found</p>
          <p className="text-sm text-[var(--text-dim)]">No agent with ID &quot;{agentId}&quot;</p>
        </Card>
      </div>
    );
  }

  const config = statusConfig[agent.status];
  const StatusIcon = config.icon;
  const tierLabel = TIER_LABELS[agent.tier] || "Other";
  const kpiEntries = Object.entries(agent.kpi_summary || {});

  return (
    <div className="space-y-6">
      {/* Back link */}
      <button onClick={() => router.push("/admin/agents")} className="text-[#6C63FF] text-sm flex items-center gap-1 hover:underline">
        <ArrowLeft size={14} /> Back to Agents
      </button>

      {/* Agent Header */}
      <div className="flex items-start gap-6">
        <HealthGaugeLarge score={agent.health_score} />
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-bold text-white">{agent.agent_name}</h1>
            <Badge variant={agent.status === "active" ? "success" : agent.status === "degraded" ? "warning" : agent.status === "inactive" ? "default" : "danger"}>
              <StatusIcon size={12} className="mr-1" />
              {config.label}
            </Badge>
          </div>
          <div className="flex items-center gap-3 text-sm text-[var(--text-dim)]">
            <span>{agent.department}</span>
            <span className="text-[10px] px-2 py-0.5 rounded bg-[rgba(108,99,255,0.15)] text-[#6C63FF]">
              Tier {agent.tier} - {tierLabel}
            </span>
          </div>
          <div className="mt-3 flex items-center gap-6 text-sm">
            <div>
              <span className="text-[var(--text-dim)]">Workflows: </span>
              <span className="text-white font-medium">{agent.workflows_monitored}</span>
            </div>
            <div>
              <span className="text-[var(--text-dim)]">Errors: </span>
              <span className={`font-medium ${agent.error_count > 0 ? "text-red-400" : "text-emerald-400"}`}>{agent.error_count}</span>
            </div>
            <div>
              <span className="text-[var(--text-dim)]">Last Heartbeat: </span>
              <span className="text-white">
                {agent.last_heartbeat ? formatDistanceToNow(new Date(agent.last_heartbeat), { addSuffix: true }) : "Never"}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Workflows */}
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
            <Workflow size={16} className="text-[#6C63FF]" />
            Assigned Workflows ({agent.workflow_ids.length})
          </h2>
          {agent.workflow_ids.length > 0 ? (
            <div className="space-y-2">
              {agent.workflow_ids.map((wfId) => (
                <div key={wfId} className="flex items-center justify-between px-3 py-2 rounded bg-[rgba(255,255,255,0.03)]">
                  <span className="text-sm text-white font-mono">{wfId}</span>
                  <div className="w-2 h-2 rounded-full bg-emerald-500" />
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-dim)]">No workflows assigned yet</p>
          )}
        </Card>

        {/* KPI Summary */}
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-white flex items-center gap-2 mb-4">
            <Activity size={16} className="text-[#FF6D5A]" />
            KPI Summary
          </h2>
          {kpiEntries.length > 0 ? (
            <div className="space-y-3">
              {kpiEntries.map(([key, value]) => (
                <div key={key} className="flex items-center justify-between">
                  <span className="text-sm text-[var(--text-dim)] capitalize">{key.replace(/_/g, " ")}</span>
                  <span className="text-sm text-white font-medium">{typeof value === "number" ? value.toLocaleString() : value}</span>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-[var(--text-dim)]">No KPI data yet. KPIs will populate once the orchestrator starts running.</p>
          )}
        </Card>
      </div>

      {/* Agent Info */}
      <Card className="p-5">
        <h2 className="text-sm font-semibold text-white mb-4">Agent Details</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span className="text-[var(--text-dim)] block">Agent ID</span>
            <span className="text-white font-mono text-xs">{agent.agent_id}</span>
          </div>
          <div>
            <span className="text-[var(--text-dim)] block">Department</span>
            <span className="text-white">{agent.department}</span>
          </div>
          <div>
            <span className="text-[var(--text-dim)] block">Tier</span>
            <span className="text-white">{agent.tier} - {tierLabel}</span>
          </div>
          <div>
            <span className="text-[var(--text-dim)] block">Updated</span>
            <span className="text-white">
              {agent.updated_at ? formatDistanceToNow(new Date(agent.updated_at), { addSuffix: true }) : "N/A"}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
