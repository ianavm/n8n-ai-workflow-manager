"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { CheckCircle2, XCircle, Clock, AlertTriangle } from "lucide-react";

interface Task {
  id: string;
  type: string;
  priority: string;
  title: string;
  description: string | null;
  status: string;
  related_entity_type: string | null;
  related_entity_id: string | null;
  due_at: string | null;
  created_at: string;
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-ZA", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const PRIORITY_COLORS: Record<string, string> = {
  urgent: "text-red-400 bg-red-500/20",
  high: "text-orange-400 bg-orange-500/20",
  medium: "text-yellow-400 bg-yellow-500/20",
  low: "text-gray-400 bg-gray-500/20",
};

export default function ApprovalsPage() {
  const supabase = createClient();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      const { data } = await supabase
        .from("acct_tasks")
        .select("*")
        .in("type", ["invoice_approval", "bill_approval", "payment_reconciliation", "bank_detail_change"])
        .in("status", ["open", "in_progress"])
        .order("priority", { ascending: true })
        .order("created_at", { ascending: true });
      setTasks((data as Task[]) ?? []);
      setLoading(false);
    }
    load();
  }, [supabase]);

  async function handleApproval(taskId: string, action: "approve" | "reject") {
    setActionLoading(taskId);
    const resp = await fetch(`/api/accounting/approvals/${taskId}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action }),
    });

    if (resp.ok) {
      setTasks((prev) => prev.filter((t) => t.id !== taskId));
    }
    setActionLoading(null);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Approval Centre</h1>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="h-24 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Approval Centre</h1>
        <span className="text-sm text-gray-400">{tasks.length} pending</span>
      </div>

      {tasks.length === 0 ? (
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-12 text-center">
          <CheckCircle2 className="mx-auto mb-3 text-green-500" size={40} />
          <p className="text-gray-400">All caught up! No pending approvals.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {tasks.map((task) => (
            <div
              key={task.id}
              className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 flex items-start gap-4"
            >
              <div className={`rounded-full p-2 mt-0.5 ${PRIORITY_COLORS[task.priority] ?? PRIORITY_COLORS.medium}`}>
                {task.priority === "urgent" ? <AlertTriangle size={16} /> : <Clock size={16} />}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className="text-sm font-semibold text-white">{task.title}</h3>
                  <span className={`px-2 py-0.5 rounded text-xs ${PRIORITY_COLORS[task.priority]}`}>
                    {task.priority}
                  </span>
                </div>
                {task.description && (
                  <p className="text-xs text-gray-400 mb-2 line-clamp-2">{task.description}</p>
                )}
                <div className="flex items-center gap-3 text-xs text-gray-500">
                  <span>{task.type.replace(/_/g, " ")}</span>
                  <span>&middot;</span>
                  <span>{formatDateTime(task.created_at)}</span>
                  {task.due_at && (
                    <>
                      <span>&middot;</span>
                      <span className="text-yellow-500">Due: {formatDateTime(task.due_at)}</span>
                    </>
                  )}
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={() => handleApproval(task.id, "approve")}
                  disabled={actionLoading === task.id}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-green-600 text-white text-xs font-medium hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle2 size={14} />
                  Approve
                </button>
                <button
                  onClick={() => handleApproval(task.id, "reject")}
                  disabled={actionLoading === task.id}
                  className="flex items-center gap-1.5 px-3 py-2 rounded-lg border border-red-500/30 text-red-400 text-xs font-medium hover:bg-red-500/10 disabled:opacity-50"
                >
                  <XCircle size={14} />
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
