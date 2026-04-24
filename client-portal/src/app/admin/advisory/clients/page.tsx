"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import { Users, Search, Plus, ChevronRight } from "lucide-react";

interface FAClient {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  pipeline_stage: string;
  health_score: number | null;
  phone: string | null;
  created_at: string;
  assigned_adviser: { id: string; full_name: string } | null;
}

const PIPELINE_STAGES = [
  "lead",
  "prospect",
  "discovery",
  "proposal",
  "onboarding",
  "active",
  "review",
  "churned",
];

const stageBadgeVariant = (
  stage: string
): "default" | "success" | "warning" | "danger" | "purple" | "coral" => {
  switch (stage) {
    case "active":
      return "success";
    case "lead":
    case "prospect":
      return "purple";
    case "discovery":
    case "proposal":
      return "coral";
    case "onboarding":
      return "warning";
    case "review":
      return "default";
    case "churned":
      return "danger";
    default:
      return "default";
  }
};

const healthColor = (score: number | null): string => {
  if (score === null) return "#6B7280";
  if (score >= 80) return "#10B981";
  if (score >= 60) return "#F59E0B";
  if (score >= 40) return "#F97316";
  return "#EF4444";
};

export default function AdvisoryClientsPage() {
  const [clients, setClients] = useState<FAClient[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [stageFilter, setStageFilter] = useState("");

  const fetchClients = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (search) params.set("search", search);
    if (stageFilter) params.set("pipeline_stage", stageFilter);

    const res = await fetch(`/api/advisory/clients?${params.toString()}`);
    if (res.ok) {
      const json = await res.json();
      setClients(json.data ?? []);
    }
    setLoading(false);
  }, [search, stageFilter]);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#00A651] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="relative">
          <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
          <div className="relative">
            <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
              Advisory <span className="gradient-text">Clients</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-2">
              {clients.length} {clients.length === 1 ? "client" : "clients"}{" "}
              total
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative max-w-xs w-full">
            <Search
              size={16}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]"
            />
            <input
              type="text"
              placeholder="Search clients..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 w-full"
            />
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-[#00A651] hover:bg-[#5A52E0] text-white rounded-lg text-sm font-medium transition-colors">
            <Plus size={16} />
            Add Client
          </button>
        </div>
      </div>

      {/* Stage Filter Pills */}
      <div className="filter-pills">
        <button
          className={`filter-pill ${stageFilter === "" ? "active" : ""}`}
          onClick={() => setStageFilter("")}
        >
          All
        </button>
        {PIPELINE_STAGES.map((stage) => (
          <button
            key={stage}
            className={`filter-pill ${stageFilter === stage ? "active" : ""}`}
            onClick={() => setStageFilter(stage)}
          >
            {stage.charAt(0).toUpperCase() + stage.slice(1)}
          </button>
        ))}
      </div>

      {/* Client Table */}
      {clients.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Users
            size={32}
            className="text-[var(--text-dim)] mx-auto mb-3 opacity-50"
          />
          <p className="text-sm text-[var(--text-dim)]">
            {search || stageFilter
              ? "No clients match your filters"
              : "No advisory clients yet"}
          </p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-dim)] uppercase tracking-wider">
                  Client
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-dim)] uppercase tracking-wider">
                  Email
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-dim)] uppercase tracking-wider">
                  Stage
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-dim)] uppercase tracking-wider">
                  Health
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[var(--text-dim)] uppercase tracking-wider">
                  Adviser
                </th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr
                  key={c.id}
                  className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer"
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-9 h-9 rounded-full flex items-center justify-center text-xs font-bold text-white flex-shrink-0"
                        style={{
                          background:
                            "linear-gradient(135deg, #00A651, #00D4AA)",
                        }}
                      >
                        {c.first_name[0]}
                        {c.last_name[0]}
                      </div>
                      <span className="text-sm font-medium text-white">
                        {c.first_name} {c.last_name}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--text-muted)]">
                    {c.email}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={stageBadgeVariant(c.pipeline_stage)}>
                      {c.pipeline_stage}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{
                          backgroundColor: healthColor(c.health_score),
                        }}
                      />
                      <span
                        className="text-sm font-medium"
                        style={{ color: healthColor(c.health_score) }}
                      >
                        {c.health_score ?? "--"}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-[var(--text-muted)]">
                    {c.assigned_adviser?.full_name ?? "Unassigned"}
                  </td>
                  <td className="px-4 py-3">
                    <ChevronRight size={16} className="text-[var(--text-dim)]" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
