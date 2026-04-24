"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { Workflow as WorkflowIcon } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";
import { cn } from "@/lib/utils";

interface Workflow {
  id: string;
  name: string;
  description: string | null;
  status: string;
  platform: string;
  external_id: string | null;
  created_at: string;
  updated_at: string;
}

function statusTone(status: string): "success" | "warning" | "danger" {
  if (status === "active") return "success";
  if (status === "paused") return "warning";
  return "danger";
}

function statusDotColor(status: string): string {
  if (status === "active") return "var(--accent-teal)";
  if (status === "paused") return "var(--warning)";
  return "var(--danger)";
}

export default function WorkflowsPage() {
  const supabase = createClient();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
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
        .from("workflows")
        .select("*")
        .eq("client_id", profile.id)
        .order("updated_at", { ascending: false });

      setWorkflows(data || []);
      setLoading(false);
    }
    load();
  }, [supabase]);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Operations"
        title="Workflows"
        description={
          loading
            ? "Loading your workflows…"
            : `${workflows.length} ${workflows.length === 1 ? "workflow" : "workflows"} assigned to your account.`
        }
      />

      {loading ? (
        <LoadingState variant="list" rows={4} />
      ) : workflows.length === 0 ? (
        <EmptyState
          icon={<WorkflowIcon className="size-5" />}
          title="No workflows yet"
          description="Workflows will appear here once they're assigned to your account."
        />
      ) : (
        <div className="flex flex-col gap-3">
          {workflows.map((wf) => (
            <Card key={wf.id} variant="interactive" padding="md">
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                <div className="flex items-center gap-4 min-w-0">
                  <span
                    aria-hidden
                    className={cn(
                      "size-2.5 rounded-full shrink-0",
                      wf.status === "active" && "pulse-dot",
                    )}
                    style={{ background: statusDotColor(wf.status) }}
                  />
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-foreground truncate">{wf.name}</h3>
                    {wf.description ? (
                      <p className="text-xs text-[var(--text-muted)] mt-0.5 truncate">
                        {wf.description}
                      </p>
                    ) : null}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <Badge tone={statusTone(wf.status)} appearance="soft" size="sm" className="capitalize">
                    {wf.status}
                  </Badge>
                  <Badge tone="neutral" appearance="outline" size="sm" className="capitalize">
                    {wf.platform}
                  </Badge>
                  <span className="text-xs text-[var(--text-dim)] hidden md:inline">
                    Updated {format(new Date(wf.updated_at), "MMM d, yyyy")}
                  </span>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
