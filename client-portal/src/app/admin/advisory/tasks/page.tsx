"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import { CheckSquare, AlertTriangle, Clock } from "lucide-react";
import { format } from "date-fns";

interface FATask {
  id: string;
  title: string;
  description: string | null;
  type: string;
  priority: string;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  client: { id: string; first_name: string; last_name: string } | null;
  assignee: { id: string; full_name: string } | null;
}

const TASK_STATUSES = ["pending", "in_progress", "completed", "cancelled"];
const PRIORITIES = ["low", "medium", "high", "urgent"];

const statusVariant = (
  s: string
): "default" | "success" | "warning" | "danger" | "purple" => {
  switch (s) {
    case "pending":
      return "default";
    case "in_progress":
      return "warning";
    case "completed":
      return "success";
    case "cancelled":
      return "danger";
    default:
      return "default";
  }
};

const priorityVariant = (
  p: string
): "default" | "success" | "warning" | "danger" | "coral" => {
  switch (p) {
    case "low":
      return "default";
    case "medium":
      return "warning";
    case "high":
      return "coral";
    case "urgent":
      return "danger";
    default:
      return "default";
  }
};

function isOverdue(dueDate: string | null, status: string): boolean {
  if (!dueDate || status === "completed" || status === "cancelled") return false;
  return new Date(dueDate) < new Date();
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<FATask[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");
  const [priorityFilter, setPriorityFilter] = useState("");

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);
    if (priorityFilter) params.set("priority", priorityFilter);

    const res = await fetch(`/api/advisory/tasks?${params.toString()}`);
    if (res.ok) {
      const json = await res.json();
      setTasks(json.data ?? []);
    }
    setLoading(false);
  }, [statusFilter, priorityFilter]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

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
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Advisory <span className="gradient-text">Tasks</span>
          </h1>
          <p className="text-sm text-[#B0B8C8] mt-2">
            {tasks.length} tasks across all clients
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div>
          <span className="text-xs text-[#6B7280] uppercase tracking-wider mb-1 block">
            Status
          </span>
          <div className="filter-pills">
            <button
              className={`filter-pill ${statusFilter === "" ? "active" : ""}`}
              onClick={() => setStatusFilter("")}
            >
              All
            </button>
            {TASK_STATUSES.map((s) => (
              <button
                key={s}
                className={`filter-pill ${statusFilter === s ? "active" : ""}`}
                onClick={() => setStatusFilter(s)}
              >
                {s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}
              </button>
            ))}
          </div>
        </div>
        <div>
          <span className="text-xs text-[#6B7280] uppercase tracking-wider mb-1 block">
            Priority
          </span>
          <div className="filter-pills">
            <button
              className={`filter-pill ${priorityFilter === "" ? "active" : ""}`}
              onClick={() => setPriorityFilter("")}
            >
              All
            </button>
            {PRIORITIES.map((p) => (
              <button
                key={p}
                className={`filter-pill ${priorityFilter === p ? "active" : ""}`}
                onClick={() => setPriorityFilter(p)}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Task List */}
      {tasks.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <CheckSquare
            size={32}
            className="text-[#6B7280] mx-auto mb-3 opacity-50"
          />
          <p className="text-sm text-[#6B7280]">No tasks found</p>
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[rgba(255,255,255,0.06)]">
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Task
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Client
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Priority
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Status
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Due Date
                </th>
                <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                  Assigned To
                </th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((t) => {
                const overdue = isOverdue(t.due_date, t.status);
                return (
                  <tr
                    key={t.id}
                    className={`border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors cursor-pointer ${
                      overdue ? "bg-[rgba(239,68,68,0.03)]" : ""
                    }`}
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        {overdue && (
                          <AlertTriangle
                            size={14}
                            className="text-red-400 flex-shrink-0"
                          />
                        )}
                        <div>
                          <span className="text-sm font-medium text-white block">
                            {t.title}
                          </span>
                          <span className="text-xs text-[#6B7280]">
                            {t.type.replace("_", " ")}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#B0B8C8]">
                      {t.client
                        ? `${t.client.first_name} ${t.client.last_name}`
                        : "--"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={priorityVariant(t.priority)}>
                        {t.priority}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={statusVariant(t.status)}>
                        {t.status.replace("_", " ")}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1 text-sm">
                        {t.due_date ? (
                          <>
                            <Clock size={12} className="text-[#6B7280]" />
                            <span
                              className={
                                overdue ? "text-red-400" : "text-[#B0B8C8]"
                              }
                            >
                              {format(new Date(t.due_date), "MMM d, yyyy")}
                            </span>
                          </>
                        ) : (
                          <span className="text-[#6B7280]">No due date</span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-[#B0B8C8]">
                      {t.assignee?.full_name ?? "Unassigned"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
