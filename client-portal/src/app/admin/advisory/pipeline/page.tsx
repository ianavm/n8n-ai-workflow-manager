"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { GitBranch, Clock } from "lucide-react";

interface PipelineClient {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  pipeline_stage: string;
  health_score: number | null;
  pipeline_stage_changed_at: string | null;
  assigned_adviser: { id: string; full_name: string } | null;
}

const PIPELINE_STAGES = [
  { key: "lead", label: "Lead", color: "#00A651" },
  { key: "prospect", label: "Prospect", color: "#818CF8" },
  { key: "discovery", label: "Discovery", color: "#FF6D5A" },
  { key: "proposal", label: "Proposal", color: "#F59E0B" },
  { key: "onboarding", label: "Onboarding", color: "#F97316" },
  { key: "active", label: "Active", color: "#10B981" },
  { key: "review", label: "Review", color: "#6B7280" },
  { key: "churned", label: "Churned", color: "#EF4444" },
];

function daysInStage(changedAt: string | null): number {
  if (!changedAt) return 0;
  const diff = Date.now() - new Date(changedAt).getTime();
  return Math.floor(diff / (1000 * 60 * 60 * 24));
}

const healthColor = (score: number | null): string => {
  if (score === null) return "#6B7280";
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#F59E0B";
  if (score >= 40) return "#F97316";
  return "#EF4444";
};

export default function PipelinePage() {
  const [clients, setClients] = useState<PipelineClient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchClients() {
      const res = await fetch("/api/advisory/clients");
      if (res.ok) {
        const json = await res.json();
        setClients(json.data ?? []);
      }
      setLoading(false);
    }
    fetchClients();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#00A651] border-t-transparent rounded-full" />
      </div>
    );
  }

  const clientsByStage = PIPELINE_STAGES.map((stage) => ({
    ...stage,
    clients: clients.filter((c) => c.pipeline_stage === stage.key),
  }));

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Client <span className="gradient-text">Pipeline</span>
          </h1>
          <p className="text-sm text-[#B0B8C8] mt-2">
            {clients.length} clients across {PIPELINE_STAGES.length} stages
          </p>
        </div>
      </div>

      {/* Pipeline Board */}
      <div className="flex gap-4 overflow-x-auto pb-4 scrollbar-hide">
        {clientsByStage.map((stage) => (
          <div
            key={stage.key}
            className="flex-shrink-0 w-[280px] glass-card p-0 overflow-hidden"
          >
            {/* Column Header */}
            <div
              className="px-4 py-3 flex items-center justify-between"
              style={{
                borderBottom: `2px solid ${stage.color}`,
              }}
            >
              <div className="flex items-center gap-2">
                <GitBranch size={14} style={{ color: stage.color }} />
                <span className="text-sm font-semibold text-white">
                  {stage.label}
                </span>
              </div>
              <span
                className="text-xs font-bold px-2 py-0.5 rounded-full"
                style={{
                  backgroundColor: `${stage.color}20`,
                  color: stage.color,
                }}
              >
                {stage.clients.length}
              </span>
            </div>

            {/* Cards */}
            <div className="p-2 space-y-2 max-h-[600px] overflow-y-auto">
              {stage.clients.length === 0 ? (
                <div className="text-center py-8 text-xs text-[#6B7280]">
                  No clients
                </div>
              ) : (
                stage.clients.map((client) => (
                  <div
                    key={client.id}
                    className="p-3 rounded-lg bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] hover:border-[rgba(108,99,255,0.3)] transition-colors cursor-pointer"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white truncate">
                        {client.first_name} {client.last_name}
                      </span>
                      <div className="flex items-center gap-1">
                        <div
                          className="w-2 h-2 rounded-full"
                          style={{
                            backgroundColor: healthColor(client.health_score),
                          }}
                        />
                        <span
                          className="text-xs font-medium"
                          style={{
                            color: healthColor(client.health_score),
                          }}
                        >
                          {client.health_score ?? "--"}
                        </span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-xs text-[#6B7280] truncate">
                        {client.assigned_adviser?.full_name ?? "Unassigned"}
                      </span>
                      <div className="flex items-center gap-1 text-xs text-[#6B7280]">
                        <Clock size={10} />
                        {daysInStage(client.pipeline_stage_changed_at)}d
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
