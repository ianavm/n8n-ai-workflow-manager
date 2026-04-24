"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { format } from "date-fns";

interface ActivityEntry {
  id: number;
  actor_type: string;
  actor_id: string | null;
  action: string;
  target_type: string | null;
  target_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export default function ActivityPage() {
  const [activities, setActivities] = useState<ActivityEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    async function fetchActivity() {
      const params = new URLSearchParams({ limit: "100" });
      if (filter !== "all") params.set("actor_type", filter);

      const res = await fetch(`/api/admin/activity?${params}`);
      if (res.ok) {
        setActivities(await res.json());
      }
      setLoading(false);
    }
    fetchActivity();
  }, [filter]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full" />
      </div>
    );
  }

  const actorBadge = (type: string) => {
    switch (type) {
      case "admin":
        return <Badge variant="purple">Admin</Badge>;
      case "client":
        return <Badge variant="success">Client</Badge>;
      case "api":
        return <Badge variant="default">API</Badge>;
      case "system":
        return <Badge variant="warning">System</Badge>;
      default:
        return <Badge>{type}</Badge>;
    }
  };

  function formatAction(action: string) {
    return action.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="relative">
          <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
          <div className="relative">
            <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
              Activity <span className="gradient-text">Log</span>
            </h1>
            <p className="text-base text-[var(--text-muted)] mt-2">
              Audit trail of all system events
            </p>
          </div>
        </div>
        <div className="flex gap-2">
          {["all", "admin", "client", "api", "system"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
                filter === f
                  ? "bg-[rgba(108,99,255,0.15)] text-[#6C63FF] border border-[rgba(108,99,255,0.3)]"
                  : "bg-[rgba(255,255,255,0.05)] text-[var(--text-dim)] border border-transparent hover:text-[var(--text-muted)]"
              }`}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <Card className="!p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.08)]">
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)]">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)]">Actor</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)]">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)]">Target</th>
                <th className="text-left px-4 py-3 text-xs font-semibold uppercase tracking-wider text-[var(--text-dim)]">Details</th>
              </tr>
            </thead>
            <tbody>
              {activities.map((a) => (
                <tr key={a.id} className="border-b border-[rgba(255,255,255,0.04)]">
                  <td className="px-4 py-3 text-xs text-[var(--text-dim)] whitespace-nowrap">
                    {format(new Date(a.created_at), "MMM d, h:mm a")}
                  </td>
                  <td className="px-4 py-3">{actorBadge(a.actor_type)}</td>
                  <td className="px-4 py-3 text-sm text-white">
                    {formatAction(a.action)}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-dim)]">
                    {a.target_type
                      ? `${a.target_type}${a.target_id ? `: ${a.target_id.slice(0, 8)}...` : ""}`
                      : "-"}
                  </td>
                  <td className="px-4 py-3 text-xs text-[var(--text-dim)] max-w-[200px] truncate">
                    {Object.keys(a.details).length > 0
                      ? JSON.stringify(a.details)
                      : "-"}
                  </td>
                </tr>
              ))}
              {activities.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center text-[var(--text-dim)]">
                    No activity logged yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
