"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { format } from "date-fns";
import { Bell } from "lucide-react";

interface Notification {
  id: number;
  event_type: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export default function NotificationsPage() {
  const supabase = createClient();
  const [notifications, setNotifications] = useState<Notification[]>([]);
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

      // Fetch recent events as notifications (crashes + milestones)
      const { data } = await supabase
        .from("stat_events")
        .select("id, event_type, created_at, metadata")
        .eq("client_id", profile.id)
        .order("created_at", { ascending: false })
        .limit(50);

      setNotifications(data || []);
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

  const typeConfig: Record<
    string,
    { label: string; variant: "success" | "purple" | "danger" | "warning"; icon: string }
  > = {
    workflow_crash: { label: "Crash", variant: "danger", icon: "!" },
    lead_created: { label: "New Lead", variant: "success", icon: "+" },
    message_received: { label: "Message In", variant: "purple", icon: ">" },
    message_sent: { label: "Message Out", variant: "purple", icon: "<" },
  };

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            <span className="gradient-text">Notifications</span>
          </h1>
          <p className="text-base text-[#B0B8C8] mt-2">
            Recent workflow events and alerts
          </p>
        </div>
      </div>

      {notifications.length === 0 ? (
        <Card>
          <EmptyState
            icon={<Bell size={24} />}
            title="No notifications"
            description="Recent workflow events and alerts will appear here."
          />
        </Card>
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => {
            const config = typeConfig[n.event_type] || {
              label: n.event_type,
              variant: "default" as const,
              icon: "?",
            };
            return (
              <Card key={n.id} className="!p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-start gap-3">
                    <Badge variant={config.variant}>{config.label}</Badge>
                    <div>
                      <p className="text-sm text-white">
                        {n.event_type === "workflow_crash"
                          ? (n.metadata as Record<string, string>)?.error ||
                            "Workflow error occurred"
                          : n.event_type === "lead_created"
                            ? `New lead: ${(n.metadata as Record<string, string>)?.lead_name || "Unknown"}`
                            : `${config.label} event logged`}
                      </p>
                      <p className="text-xs text-[#6B7280] mt-1">
                        {format(new Date(n.created_at), "MMM d, yyyy 'at' h:mm a")}
                      </p>
                    </div>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
