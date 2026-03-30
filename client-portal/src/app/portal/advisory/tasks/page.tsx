"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  CheckSquare,
  Circle,
  CheckCircle,
  Clock,
  Filter,
} from "lucide-react";

interface FaTask {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string | null;
  due_date: string | null;
  created_at: string;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

type TaskFilter = "all" | "pending" | "completed";

function priorityColor(priority: string | null): string {
  if (!priority) return "#6B7280";
  const p = priority.toLowerCase();
  if (p === "high" || p === "urgent") return "#EF4444";
  if (p === "medium") return "#F59E0B";
  return "#10B981";
}

function isOverdue(dueDate: string | null, status: string): boolean {
  if (!dueDate || status === "completed") return false;
  return new Date(dueDate) < new Date();
}

export default function AdvisoryTasks() {
  const supabase = createClient();
  const [tasks, setTasks] = useState<FaTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [completingId, setCompletingId] = useState<string | null>(null);

  const fetchTasks = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("portal_client_id", userData.user.id)
      .single();

    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: taskData, error: taskErr } = await supabase
      .from("fa_tasks")
      .select("id, title, description, status, priority, due_date, created_at")
      .eq("client_id", client.id)
      .order("created_at", { ascending: false });

    if (taskErr) {
      setError(taskErr.message);
      setLoading(false);
      return;
    }

    setTasks(taskData || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  async function markComplete(taskId: string) {
    setCompletingId(taskId);
    const { error: updateErr } = await supabase
      .from("fa_tasks")
      .update({ status: "completed" })
      .eq("id", taskId);

    if (!updateErr) {
      setTasks((prev) =>
        prev.map((t) => (t.id === taskId ? { ...t, status: "completed" } : t))
      );
    }
    setCompletingId(null);
  }

  const filtered = tasks.filter((t) => {
    if (filter === "pending") return t.status !== "completed";
    if (filter === "completed") return t.status === "completed";
    return true;
  });

  const filterBtnStyle = (active: boolean): React.CSSProperties => ({
    padding: "6px 14px",
    borderRadius: "8px",
    fontSize: "13px",
    fontWeight: 500,
    border: "1px solid",
    borderColor: active ? "rgba(108,99,255,0.3)" : "rgba(255,255,255,0.08)",
    background: active ? "rgba(108,99,255,0.15)" : "transparent",
    color: active ? "#fff" : "#6B7280",
    cursor: "pointer",
    fontFamily: "inherit",
  });

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #6C63FF",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Tasks</h1>
          <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
            Action items from your advisory meetings.
          </p>
        </div>
        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
          <Filter size={14} style={{ color: "#6B7280" }} />
          <button style={filterBtnStyle(filter === "all")} onClick={() => setFilter("all")}>All</button>
          <button style={filterBtnStyle(filter === "pending")} onClick={() => setFilter("pending")}>Pending</button>
          <button style={filterBtnStyle(filter === "completed")} onClick={() => setFilter("completed")}>Completed</button>
        </div>
      </div>

      {filtered.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <CheckSquare size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No tasks found.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {filtered.map((t) => {
            const done = t.status === "completed";
            const overdue = isOverdue(t.due_date, t.status);

            return (
              <div
                key={t.id}
                style={{
                  ...glassCard,
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "14px",
                  padding: "16px 20px",
                  opacity: done ? 0.6 : 1,
                }}
              >
                {/* Status icon / complete button */}
                <button
                  onClick={() => !done && markComplete(t.id)}
                  disabled={done || completingId === t.id}
                  style={{
                    background: "none",
                    border: "none",
                    cursor: done ? "default" : "pointer",
                    padding: "2px",
                    flexShrink: 0,
                    marginTop: "2px",
                    color: done ? "#10B981" : "#6B7280",
                  }}
                  title={done ? "Completed" : "Mark as complete"}
                >
                  {done ? <CheckCircle size={20} /> : <Circle size={20} />}
                </button>

                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
                    <span
                      style={{
                        fontSize: "14px",
                        fontWeight: 600,
                        color: done ? "#6B7280" : "#fff",
                        textDecoration: done ? "line-through" : "none",
                      }}
                    >
                      {t.title}
                    </span>
                    {t.priority && (
                      <span
                        style={{
                          fontSize: "11px",
                          fontWeight: 600,
                          padding: "2px 8px",
                          borderRadius: "4px",
                          background: `${priorityColor(t.priority)}15`,
                          color: priorityColor(t.priority),
                          textTransform: "uppercase",
                        }}
                      >
                        {t.priority}
                      </span>
                    )}
                  </div>
                  {t.description && (
                    <p style={{ fontSize: "13px", color: "#6B7280", margin: "4px 0 0", lineHeight: "1.5" }}>
                      {t.description}
                    </p>
                  )}
                  {t.due_date && (
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "6px",
                        marginTop: "8px",
                        fontSize: "12px",
                        color: overdue ? "#EF4444" : "#6B7280",
                      }}
                    >
                      <Clock size={12} />
                      Due {new Date(t.due_date).toLocaleDateString("en-ZA", { day: "numeric", month: "short", year: "numeric" })}
                      {overdue && <span style={{ fontWeight: 600 }}>(Overdue)</span>}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
