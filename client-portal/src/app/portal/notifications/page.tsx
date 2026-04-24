"use client";

import { useEffect, useState } from "react";
import { format } from "date-fns";
import { AlertTriangle, Bell, MessageCircle, Send, UserPlus } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";

interface Notification {
  id: number;
  event_type: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

const TYPE_CONFIG: Record<
  string,
  { label: string; tone: "success" | "danger" | "info" | "warning"; icon: LucideIcon; color: string }
> = {
  workflow_crash:    { label: "Crash",        tone: "danger",  icon: AlertTriangle,  color: "var(--danger)" },
  lead_created:      { label: "New lead",     tone: "success", icon: UserPlus,       color: "var(--accent-teal)" },
  message_received:  { label: "Message in",   tone: "info",    icon: MessageCircle,  color: "var(--accent-purple)" },
  message_sent:      { label: "Message out",  tone: "info",    icon: Send,           color: "var(--accent-purple)" },
};

function describe(n: Notification): string {
  const meta = (n.metadata ?? {}) as Record<string, string>;
  if (n.event_type === "workflow_crash") return meta.error || "Workflow error occurred";
  if (n.event_type === "lead_created")   return `New lead: ${meta.lead_name || "Unknown"}`;
  return `${(TYPE_CONFIG[n.event_type] ?? { label: n.event_type }).label} event logged`;
}

export default function NotificationsPage() {
  const supabase = createClient();
  const [notifications, setNotifications] = useState<Notification[]>([]);
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
        .from("stat_events")
        .select("id, event_type, created_at, metadata")
        .eq("client_id", profile.id)
        .order("created_at", { ascending: false })
        .limit(50);

      setNotifications(data || []);
      setLoading(false);
    }
    load();
  }, [supabase]);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Account"
        title="Notifications"
        description="Recent workflow events and alerts across your account."
        actions={
          notifications.length > 0 ? (
            <Badge tone="neutral" appearance="soft">
              {notifications.length} recent
            </Badge>
          ) : null
        }
      />

      {loading ? (
        <LoadingState variant="list" rows={6} />
      ) : notifications.length === 0 ? (
        <EmptyState
          icon={<Bell className="size-5" />}
          title="No notifications yet"
          description="Recent workflow events and alerts will appear here."
        />
      ) : (
        <ul className="flex flex-col gap-2.5">
          {notifications.map((n) => {
            const cfg = TYPE_CONFIG[n.event_type] ?? {
              label: n.event_type,
              tone: "info" as const,
              icon: Bell,
              color: "var(--text-muted)",
            };
            const Icon = cfg.icon;
            return (
              <li key={n.id}>
                <Card variant="default" padding="md">
                  <div className="flex items-start gap-3">
                    <span
                      className="grid place-items-center size-9 rounded-[var(--radius-sm)] shrink-0"
                      style={{
                        background: `color-mix(in srgb, ${cfg.color} 12%, transparent)`,
                        color: cfg.color,
                      }}
                    >
                      <Icon className="size-4" aria-hidden />
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <Badge tone={cfg.tone} appearance="soft" size="sm">
                          {cfg.label}
                        </Badge>
                        <span className="text-sm font-medium text-foreground">{describe(n)}</span>
                      </div>
                      <p className="text-xs text-[var(--text-dim)] mt-1">
                        {format(new Date(n.created_at), "MMM d, yyyy 'at' h:mm a")}
                      </p>
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
