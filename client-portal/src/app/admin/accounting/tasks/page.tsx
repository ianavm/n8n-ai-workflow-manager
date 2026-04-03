"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { ListTodo, RefreshCw, CheckCircle2, AlertTriangle } from "lucide-react";

interface Task {
  id: string;
  type: string;
  priority: string;
  status: string;
  title: string;
  description: string | null;
  owner: string | null;
  related_entity_type: string | null;
  due_at: string | null;
  created_at: string;
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-ZA", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

const STATUS_COLORS: Record<string, string> = {
  open: "text-blue-300 bg-blue-500/20",
  in_progress: "text-yellow-300 bg-yellow-500/20",
  completed: "text-green-300 bg-green-500/20",
  escalated: "text-red-300 bg-red-500/20",
  cancelled: "text-gray-400 bg-gray-500/20",
};

export default function TasksPage() {
  const supabase = createClient();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<"active" | "all">("active");

  useEffect(() => {
    async function load() {
      let query = supabase
        .from("acct_tasks")
        .select("*")
        .order("created_at", { ascending: false })
        .limit(100);

      if (filter === "active") {
        query = query.in("status", ["open", "in_progress", "escalated"]);
      }

      const { data } = await query;
      setTasks((data as Task[]) ?? []);
      setLoading(false);
    }
    load();
  }, [supabase, filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Task & Exception Queue</h1>
        <div className="flex gap-2">
          <button
            onClick={() => setFilter("active")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium ${
              filter === "active" ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A]" : "text-gray-400"
            }`}
          >
            Active
          </button>
          <button
            onClick={() => setFilter("all")}
            className={`px-3 py-1.5 text-xs rounded-lg font-medium ${
              filter === "all" ? "bg-[rgba(255,109,90,0.15)] text-[#FF6D5A]" : "text-gray-400"
            }`}
          >
            All
          </button>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-20 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />
          ))}
        </div>
      ) : tasks.length === 0 ? (
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-12 text-center">
          <CheckCircle2 className="mx-auto mb-3 text-green-500" size={40} />
          <p className="text-gray-400">No {filter === "active" ? "active" : ""} tasks</p>
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-4 flex items-center gap-4">
              <div className={`rounded-full p-2 shrink-0 ${
                task.status === "escalated" ? "bg-red-500/20" : "bg-yellow-500/20"
              }`}>
                {task.status === "escalated" ? (
                  <AlertTriangle size={16} className="text-red-400" />
                ) : (
                  <ListTodo size={16} className="text-yellow-400" />
                )}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="text-sm font-medium text-white truncate">{task.title}</h3>
                  <span className={`px-2 py-0.5 rounded text-xs ${STATUS_COLORS[task.status]}`}>
                    {task.status}
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-gray-500 mt-1">
                  <span>{task.type.replace(/_/g, " ")}</span>
                  <span>{task.priority}</span>
                  {task.owner && <span>Assigned: {task.owner}</span>}
                  <span>{formatDateTime(task.created_at)}</span>
                </div>
              </div>
              {task.status !== "completed" && task.status !== "cancelled" && (
                <button className="shrink-0 flex items-center gap-1 px-3 py-1.5 rounded-lg border border-[rgba(255,255,255,0.1)] text-xs text-gray-300 hover:bg-[rgba(255,255,255,0.05)]">
                  <RefreshCw size={12} /> Retry
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
