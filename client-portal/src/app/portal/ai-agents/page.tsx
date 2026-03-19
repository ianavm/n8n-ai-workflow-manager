"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { StatCard } from "@/components/charts/StatCard";
import { Skeleton } from "@/components/ui/Skeleton";
import { Bot, Users, Wifi, WifiOff, Clock, Phone } from "lucide-react";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";

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

function getEffectiveStatus(agent: AgentProfile): {
  label: string;
  variant: "success" | "danger" | "warning";
  aiActive: boolean;
} {
  if (agent.manual_override) {
    const expiry = agent.manual_override_expiry
      ? new Date(agent.manual_override_expiry)
      : null;
    const expired = expiry && expiry.getTime() < Date.now();

    if (!expired) {
      if (agent.manual_override === "online") {
        return { label: "Online", variant: "success", aiActive: false };
      }
      return { label: "Offline", variant: "danger", aiActive: true };
    }
  }
  // No override or expired — auto mode
  return { label: "Auto", variant: "warning", aiActive: true };
}

function getOverrideTimeLeft(expiry: string | null): string | null {
  if (!expiry) return null;
  const expiryDate = new Date(expiry);
  if (expiryDate.getTime() < Date.now()) return null;
  return formatDistanceToNow(expiryDate, { addSuffix: false });
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
    if (!user) return;

    const { data: profile } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", user.id)
      .single();

    if (!profile) return;

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

    // Optimistic update
    setAgents((prev) =>
      prev.map((a) =>
        a.agent_id === agent.agent_id
          ? {
              ...a,
              manual_override: newAction,
              manual_override_expiry: new Date(
                Date.now() + 12 * 3600 * 1000
              ).toISOString(),
              is_online: newAction === "online",
              updated_at: new Date().toISOString(),
            }
          : a
      )
    );

    try {
      const res = await fetch("/api/portal/agent-toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentId: agent.agent_id, action: newAction }),
      });

      if (!res.ok) {
        throw new Error("Toggle failed");
      }

      toast.success(
        newAction === "online"
          ? `${agent.agent_name} is now online — AI stepped back`
          : `${agent.agent_name} is now offline — AI is handling messages`
      );
    } catch {
      // Revert optimistic update
      fetchAgents();
      toast.error("Failed to toggle agent status");
    } finally {
      setToggling(null);
    }
  }

  const onlineCount = agents.filter(
    (a) => getEffectiveStatus(a).label === "Online"
  ).length;
  const aiActiveCount = agents.filter(
    (a) => getEffectiveStatus(a).aiActive
  ).length;

  return (
    <div className="max-w-7xl space-y-6">
      {/* Header */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            AI <span className="gradient-text">Agents</span>
          </h1>
          <p className="text-sm text-[#6B7280] mt-2">
            Toggle your agents online or offline. When offline, the AI assistant
            handles messages automatically.
          </p>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
        <StatCard
          title="Total Agents"
          value={agents.length}
          icon={<Users size={20} />}
          color="purple"
          loading={loading}
        />
        <StatCard
          title="Currently Online"
          value={onlineCount}
          icon={<Wifi size={20} />}
          color="teal"
          loading={loading}
        />
        <StatCard
          title="AI Handling"
          value={aiActiveCount}
          icon={<Bot size={20} />}
          color="coral"
          loading={loading}
        />
      </div>

      {/* Agent cards */}
      {loading ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {[1, 2].map((i) => (
            <Card key={i} hover={false}>
              <div className="space-y-5">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-6 w-40" />
                  <Skeleton className="h-8 w-16 rounded-full" />
                </div>
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-48" />
              </div>
            </Card>
          ))}
        </div>
      ) : agents.length === 0 ? (
        <Card>
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="w-14 h-14 rounded-2xl bg-[rgba(108,99,255,0.1)] border border-[rgba(108,99,255,0.2)] flex items-center justify-center mb-4">
              <Bot size={28} className="text-[#6C63FF]" />
            </div>
            <h2 className="text-lg font-semibold text-white mb-2">
              No Agents Configured
            </h2>
            <p className="text-sm text-[#6B7280] max-w-md">
              Your AI agents will appear here once they have been set up. Contact
              your administrator to get started.
            </p>
          </div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
          {agents.map((agent, index) => {
            const status = getEffectiveStatus(agent);
            const timeLeft = getOverrideTimeLeft(
              agent.manual_override_expiry
            );
            const isToggling = toggling === agent.agent_id;

            return (
              <Card
                key={agent.id}
                hover={false}
                className={`stagger-${Math.min(index + 1, 5)}`}
                padding="none"
              >
                <div className="p-7">
                  {/* Top row: name + toggle */}
                  <div className="flex items-start justify-between mb-5">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-xl flex items-center justify-center"
                        style={{
                          backgroundColor:
                            status.variant === "success"
                              ? "rgba(16, 185, 129, 0.1)"
                              : status.variant === "danger"
                              ? "rgba(239, 68, 68, 0.1)"
                              : "rgba(245, 158, 11, 0.1)",
                          border: `1px solid ${
                            status.variant === "success"
                              ? "rgba(16, 185, 129, 0.2)"
                              : status.variant === "danger"
                              ? "rgba(239, 68, 68, 0.2)"
                              : "rgba(245, 158, 11, 0.2)"
                          }`,
                        }}
                      >
                        <Bot
                          size={20}
                          style={{
                            color:
                              status.variant === "success"
                                ? "#10B981"
                                : status.variant === "danger"
                                ? "#EF4444"
                                : "#F59E0B",
                          }}
                        />
                      </div>
                      <div>
                        <h3 className="text-base font-semibold text-white">
                          {agent.agent_name}
                        </h3>
                        {agent.phone_number && (
                          <p className="text-xs text-[#6B7280] flex items-center gap-1 mt-1">
                            <Phone size={10} />
                            {agent.phone_number}
                          </p>
                        )}
                      </div>
                    </div>

                    {/* Toggle switch */}
                    <button
                      onClick={() => handleToggle(agent)}
                      disabled={isToggling}
                      className={`relative w-14 h-7 rounded-full transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-[#0A0F1C] ${
                        status.label === "Online"
                          ? "bg-emerald-500 focus:ring-emerald-500/50"
                          : "bg-[rgba(255,255,255,0.12)] focus:ring-[rgba(255,255,255,0.2)]"
                      } ${isToggling ? "opacity-50 cursor-wait" : "cursor-pointer"}`}
                      aria-label={`Toggle ${agent.agent_name} ${
                        status.label === "Online" ? "offline" : "online"
                      }`}
                    >
                      <span
                        className={`absolute top-0.5 w-6 h-6 rounded-full bg-white shadow-md transition-transform duration-300 ${
                          status.label === "Online"
                            ? "translate-x-7"
                            : "translate-x-0.5"
                        }`}
                      />
                    </button>
                  </div>

                  {/* Status + business hours */}
                  <div className="flex flex-wrap items-center gap-2 mb-4">
                    <Badge variant={status.variant} pulse={status.label === "Online"}>
                      {status.label === "Online" && <Wifi size={10} />}
                      {status.label === "Offline" && <WifiOff size={10} />}
                      {status.label === "Auto" && <Clock size={10} />}
                      {status.label}
                    </Badge>
                    <span className="text-xs text-[#6B7280]">
                      <Clock size={10} className="inline mr-1" />
                      Mon-Fri {agent.business_hours_start} -{" "}
                      {agent.business_hours_end}
                    </span>
                  </div>

                  {/* Override expiry */}
                  {timeLeft && agent.manual_override && (
                    <p className="text-xs text-amber-400 mb-2">
                      Override expires in {timeLeft}
                    </p>
                  )}

                  {/* AI status message */}
                  <div
                    className={`text-xs px-3 py-2 rounded-lg ${
                      status.aiActive
                        ? "bg-[rgba(108,99,255,0.08)] text-[#9B93FF] border border-[rgba(108,99,255,0.15)]"
                        : "bg-[rgba(16,185,129,0.08)] text-emerald-400 border border-emerald-500/15"
                    }`}
                  >
                    {status.aiActive
                      ? "AI is handling incoming messages"
                      : "Agent is responding directly"}
                  </div>
                </div>

                {/* Footer */}
                <div className="px-6 py-3 border-t border-[rgba(255,255,255,0.06)] flex items-center justify-between">
                  <span className="text-xs text-[#6B7280]">
                    Last updated{" "}
                    {formatDistanceToNow(new Date(agent.updated_at), {
                      addSuffix: true,
                    })}
                  </span>
                  {agent.email && (
                    <span className="text-xs text-[#6B7280]">
                      {agent.email}
                    </span>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
