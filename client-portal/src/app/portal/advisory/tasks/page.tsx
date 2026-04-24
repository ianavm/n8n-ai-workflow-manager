"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle, CheckSquare, Circle, Clock } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui-shadcn/tabs";
import { cn } from "@/lib/utils";

interface FaTask {
  id: string;
  title: string;
  description: string | null;
  status: string;
  priority: string | null;
  due_date: string | null;
  created_at: string;
}

type TaskFilter = "all" | "pending" | "completed";

function priorityTone(priority: string | null): "danger" | "warning" | "success" | "neutral" {
  if (!priority) return "neutral";
  const p = priority.toLowerCase();
  if (p === "high" || p === "urgent") return "danger";
  if (p === "medium") return "warning";
  return "success";
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

    const { data: portalClient } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", userData.user.id)
      .single();
    if (!portalClient) {
      setError("No portal account found");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", portalClient.id)
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
      setTasks((prev) => prev.map((t) => (t.id === taskId ? { ...t, status: "completed" } : t)));
    }
    setCompletingId(null);
  }

  const filtered = tasks.filter((t) => {
    if (filter === "pending") return t.status !== "completed";
    if (filter === "completed") return t.status === "completed";
    return true;
  });

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Tasks" description="Action items from your advisory meetings." />
        <LoadingState variant="list" rows={4} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Tasks" description="Action items from your advisory meetings." />
        <ErrorState title="Unable to load tasks" description={error} onRetry={fetchTasks} />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Advisory"
        title="Tasks"
        description="Action items from your advisory meetings."
        actions={
          <Tabs value={filter} onValueChange={(v) => setFilter(v as TaskFilter)}>
            <TabsList>
              <TabsTrigger value="all">All</TabsTrigger>
              <TabsTrigger value="pending">Pending</TabsTrigger>
              <TabsTrigger value="completed">Completed</TabsTrigger>
            </TabsList>
          </Tabs>
        }
      />

      {filtered.length === 0 ? (
        <EmptyState icon={<CheckSquare className="size-5" />} title="No tasks found" />
      ) : (
        <ul className="flex flex-col gap-2.5">
          {filtered.map((t) => {
            const done = t.status === "completed";
            const overdue = isOverdue(t.due_date, t.status);
            return (
              <li key={t.id}>
                <Card variant="default" padding="md" className={cn(done && "opacity-60")}>
                  <div className="flex items-start gap-3">
                    <button
                      onClick={() => !done && markComplete(t.id)}
                      disabled={done || completingId === t.id}
                      title={done ? "Completed" : "Mark as complete"}
                      className={cn(
                        "shrink-0 mt-0.5 transition-colors",
                        done
                          ? "text-[var(--accent-teal)] cursor-default"
                          : "text-[var(--text-dim)] hover:text-[var(--accent-teal)]",
                      )}
                    >
                      {done ? <CheckCircle className="size-5" /> : <Circle className="size-5" />}
                    </button>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span
                          className={cn(
                            "text-sm font-semibold",
                            done ? "line-through text-[var(--text-dim)]" : "text-foreground",
                          )}
                        >
                          {t.title}
                        </span>
                        {t.priority ? (
                          <Badge tone={priorityTone(t.priority)} appearance="soft" size="sm" className="uppercase">
                            {t.priority}
                          </Badge>
                        ) : null}
                      </div>
                      {t.description ? (
                        <p className="text-sm text-[var(--text-muted)] mt-1 leading-relaxed">
                          {t.description}
                        </p>
                      ) : null}
                      {t.due_date ? (
                        <p
                          className={cn(
                            "mt-2 inline-flex items-center gap-1.5 text-xs",
                            overdue ? "text-[var(--danger)]" : "text-[var(--text-dim)]",
                          )}
                        >
                          <Clock className="size-3" />
                          Due {new Date(t.due_date).toLocaleDateString("en-ZA", {
                            day: "numeric",
                            month: "short",
                            year: "numeric",
                          })}
                          {overdue ? <span className="font-semibold">(Overdue)</span> : null}
                        </p>
                      ) : null}
                    </div>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
