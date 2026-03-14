"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { format } from "date-fns";
import { Workflow } from "lucide-react";

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

export default function WorkflowsPage() {
  const supabase = createClient();
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetch() {
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
        .from("workflows")
        .select("*")
        .eq("client_id", profile.id)
        .order("updated_at", { ascending: false });

      setWorkflows(data || []);
      setLoading(false);
    }
    fetch();
  }, [supabase]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full" />
      </div>
    );
  }

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "paused" ? "warning" : "danger";

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Your <span className="gradient-text">Workflows</span>
          </h1>
          <p className="text-base text-[#B0B8C8] mt-2">
            {workflows.length} {workflows.length === 1 ? "workflow" : "workflows"} assigned
          </p>
        </div>
      </div>

      {workflows.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Workflow size={24} />}
            title="No workflows yet"
            description="Workflows will appear here once they're assigned to your account."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {workflows.map((wf) => (
            <Card key={wf.id}>
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div
                    className={`w-3 h-3 rounded-full flex-shrink-0 ${
                      wf.status === "active"
                        ? "bg-emerald-400"
                        : wf.status === "paused"
                          ? "bg-amber-400"
                          : "bg-red-400"
                    }`}
                  />
                  <div>
                    <h3 className="text-white font-medium">{wf.name}</h3>
                    {wf.description && (
                      <p className="text-xs text-[#6B7280] mt-0.5">
                        {wf.description}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex items-center gap-3 sm:flex-shrink-0">
                  <Badge variant={statusVariant(wf.status)}>{wf.status}</Badge>
                  <span className="text-xs text-[#6B7280]">
                    {wf.platform}
                  </span>
                  <span className="text-xs text-[#6B7280]">
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
