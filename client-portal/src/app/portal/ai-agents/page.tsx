"use client";

import { useCallback, useEffect, useState } from "react";
import { Bot, Clock, Phone, Users, Wifi, WifiOff } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { KPIGrid } from "@/components/portal/KPIGrid";
import { StatCard } from "@/components/portal/StatCard";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";
import { Switch } from "@/components/ui-shadcn/switch";
import { cn } from "@/lib/utils";

interface AgentProfile {
  id: string;
  agent_id: string;
  agent_name: string;
  phone_number: string | null;
  email: string | null;
  is_online: boolean;
  manual_override: "online" | "offline" | null;
  manual_override_expiry: string | null;
  business_hours_start: string;
  business_hours_end: string;
  timezone: string;
  updated_at: string;
}

type EffectiveStatus = {
  label: "Online" | "Offline" | "Auto";
  tone: "success" | "danger" | "warning";
  aiActive: boolean;
};

function getEffectiveStatus(agent: AgentProfile): EffectiveStatus {
  if (agent.manual_override) {
    const expiry = agent.manual_override_expiry ? new Date(agent.manual_override_expiry) : null;
    const expired = expiry && expiry.getTime() < Date.now();
    if (!expired) {
      if (agent.manual_override === "online") return { label: "Online", tone: "success", aiActive: false };
      return { label: "Offline", tone: "danger", aiActive: true };
    }
  }
  return { label: "Auto", tone: "warning", aiActive: true };
}

function getOverrideTimeLeft(expiry: string | null): string | null {
  if (!expiry) return null;
  const d = new Date(expiry);
  if (d.getTime() < Date.now()) return null;
  return formatDistanceToNow(d, { addSuffix: false });
}

export default function AIAgentsPage() {
  const supabase = createClient();
  const [agents, setAgents] = useState<AgentProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<string | null>(null);

  const fetchAgents = useCallback(async () => {
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) {
      setLoading(false);
      return;
    }

    const { data: profile } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .single();

    if (!profile) {
      setLoading(false);
      return;
    }

    const { data } = await supabase
      .from("agent_profiles")
      .select("*")
      .eq("client_id", profile.id)
      .order("agent_name");

    setAgents((data as AgentProfile[]) || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchAgents();
  }, [fetchAgents]);

  async function handleToggle(agent: AgentProfile) {
    const status = getEffectiveStatus(agent);
    const newAction = status.aiActive ? "online" : "offline";
    setToggling(agent.agent_id);

    setAgents((prev) =>
      prev.map((a) =>
        a.agent_id === agent.agent_id
          ? {
              ...a,
              manual_override: newAction,
              manual_override_expiry: new Date(Date.now() + 12 * 3600 * 1000).toISOString(),
              is_online: newAction === "online",
              updated_at: new Date().toISOString(),
            }
          : a,
      ),
    );

    try {
      const res = await fetch("/api/portal/agent-toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: agent.agent_id, action: newAction }),
      });
      if (!res.ok) throw new Error("Toggle failed");

      toast.success(
        newAction === "online"
          ? `${agent.agent_name} is now online — AI stepped back`
          : `${agent.agent_name} is now offline — AI is handling messages`,
      );
    } catch {
      fetchAgents();
      toast.error("Failed to toggle agent status");
    } finally {
      setToggling(null);
    }
  }

  const onlineCount = agents.filter((a) => getEffectiveStatus(a).label === "Online").length;
  const aiActiveCount = agents.filter((a) => getEffectiveStatus(a).aiActive).length;

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Operations"
        title="AI agents"
        description="Toggle agents online or offline. When offline, the AI assistant handles messages automatically."
      />

      {/* Stat row */}
      <KPIGrid cols={3}>
        <StatCard
          label="Total agents"
          value={agents.length}
          icon={<Users className="size-4" aria-hidden />}
          accent="purple"
          loading={loading}
        />
        <StatCard
          label="Currently online"
          value={onlineCount}
          icon={<Wifi className="size-4" aria-hidden />}
          accent="teal"
          loading={loading}
        />
        <StatCard
          label="AI handling"
          value={aiActiveCount}
          icon={<Bot className="size-4" aria-hidden />}
          accent="coral"
          loading={loading}
        />
      </KPIGrid>

      {loading ? (
        <LoadingState variant="list" rows={3} />
      ) : agents.length === 0 ? (
        <EmptyState
          icon={<Bot className="size-5" />}
          title="No agents configured"
          description="Your AI agents will appear here once they've been set up. Contact your administrator to get started."
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {agents.map((agent) => {
            const status = getEffectiveStatus(agent);
            const timeLeft = getOverrideTimeLeft(agent.manual_override_expiry);
            const isToggling = toggling === agent.agent_id;
            const statusColor =
              status.tone === "success"
                ? "var(--accent-teal)"
                : status.tone === "danger"
                  ? "var(--danger)"
                  : "var(--warning)";

            return (
              <Card key={agent.id} variant="default" padding="none" className="flex flex-col">
                <div className="p-5">
                  <div className="flex items-start justify-between mb-4 gap-3">
                    <div className="flex items-center gap-3 min-w-0">
                      <span
                        className="grid place-items-center size-10 rounded-[var(--radius-sm)] shrink-0"
                        style={{
                          background: `color-mix(in srgb, ${statusColor} 12%, transparent)`,
                          color: statusColor,
                          borderColor: `color-mix(in srgb, ${statusColor} 25%, transparent)`,
                          borderWidth: 1,
                          borderStyle: "solid",
                        }}
                      >
                        <Bot className="size-4" aria-hidden />
                      </span>
                      <div className="min-w-0">
                        <h3 className="text-sm font-semibold text-foreground truncate">
                          {agent.agent_name}
                        </h3>
                        {agent.phone_number ? (
                          <p className="flex items-center gap-1 text-xs text-[var(--text-dim)] mt-0.5">
                            <Phone className="size-3" />
                            {agent.phone_number}
                          </p>
                        ) : null}
                      </div>
                    </div>

                    <Switch
                      checked={status.label === "Online"}
                      onCheckedChange={() => handleToggle(agent)}
                      disabled={isToggling}
                      aria-label={`Toggle ${agent.agent_name} ${
                        status.label === "Online" ? "offline" : "online"
                      }`}
                      className={cn(isToggling && "opacity-50")}
                    />
                  </div>

                  <div className="flex flex-wrap items-center gap-2 mb-3">
                    <Badge tone={status.tone} appearance="soft" size="sm">
                      {status.label === "Online" ? (
                        <Wifi className="size-3" />
                      ) : status.label === "Offline" ? (
                        <WifiOff className="size-3" />
                      ) : (
                        <Clock className="size-3" />
                      )}
                      {status.label}
                    </Badge>
                    <span className="text-xs text-[var(--text-dim)] inline-flex items-center gap-1">
                      <Clock className="size-3" />
                      Mon–Fri {agent.business_hours_start} – {agent.business_hours_end}
                    </span>
                  </div>

                  {timeLeft && agent.manual_override ? (
                    <p className="text-xs text-[var(--warning)] mb-2">
                      Override expires in {timeLeft}
                    </p>
                  ) : null}

                  <div
                    className={cn(
                      "text-xs px-3 py-2 rounded-[var(--radius-sm)] border",
                      status.aiActive
                        ? "bg-[color-mix(in_srgb,var(--accent-purple)_8%,transparent)] text-[var(--accent-purple)] border-[color-mix(in_srgb,var(--accent-purple)_20%,transparent)]"
                        : "bg-[color-mix(in_srgb,var(--accent-teal)_8%,transparent)] text-[var(--accent-teal)] border-[color-mix(in_srgb,var(--accent-teal)_20%,transparent)]",
                    )}
                  >
                    {status.aiActive ? "AI is handling incoming messages" : "Agent is responding directly"}
                  </div>
                </div>

                <div className="px-5 py-3 border-t border-[var(--border-subtle)] flex items-center justify-between text-xs text-[var(--text-dim)]">
                  <span>
                    Last updated {formatDistanceToNow(new Date(agent.updated_at), { addSuffix: true })}
                  </span>
                  {agent.email ? <span className="truncate ml-3">{agent.email}</span> : null}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
