"use client";

import {
  FileText,
  Mail,
  Phone,
  Calendar,
  ArrowRight,
  Zap,
  MessageCircle,
} from "lucide-react";

interface Activity {
  id: string;
  activity_type: string;
  title: string;
  notes: string | null;
  actor: string;
  created_at: string;
  metadata: Record<string, unknown> | null;
}

interface ActivityTimelineProps {
  activities: Activity[];
}

const ICON_MAP: Record<string, typeof FileText> = {
  note: FileText,
  email_sent: Mail,
  call: Phone,
  whatsapp: MessageCircle,
  meeting: Calendar,
  stage_change: ArrowRight,
  system: Zap,
};

const ICON_COLOR_MAP: Record<string, string> = {
  note: "#6366F1",
  email_sent: "#3B82F6",
  call: "#F59E0B",
  whatsapp: "#22C55E",
  meeting: "#A855F7",
  stage_change: "#10B981",
  system: "#6B7280",
};

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;

  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;

  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;

  return date.toLocaleDateString("en-ZA", {
    day: "numeric",
    month: "short",
    year: diffDays > 365 ? "numeric" : undefined,
  });
}

export function ActivityTimeline({ activities }: ActivityTimelineProps) {
  if (activities.length === 0) {
    return (
      <div className="text-center py-8 text-[#6B7280] text-sm">
        No activities yet
      </div>
    );
  }

  return (
    <div className="relative">
      {/* Vertical line */}
      <div
        className="absolute left-4 top-0 bottom-0 w-px"
        style={{ background: "rgba(255,255,255,0.08)" }}
      />

      <div className="space-y-4">
        {activities.map((activity) => {
          const Icon = ICON_MAP[activity.activity_type] ?? Zap;
          const iconColor = ICON_COLOR_MAP[activity.activity_type] ?? "#6B7280";

          return (
            <div key={activity.id} className="relative flex items-start gap-3 pl-1">
              {/* Dot */}
              <div
                className="relative z-10 flex items-center justify-center w-7 h-7 rounded-full shrink-0"
                style={{ backgroundColor: `${iconColor}26` }}
              >
                <Icon size={14} style={{ color: iconColor }} />
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 pt-0.5">
                <p className="text-sm text-white">{activity.title}</p>
                {activity.notes && (
                  <p className="text-xs text-[#B0B8C8] mt-1 whitespace-pre-wrap">
                    {activity.notes}
                  </p>
                )}
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-[10px] text-[#6B7280]">
                    {activity.actor}
                  </span>
                  <span className="text-[10px] text-[#6B7280]">
                    {formatRelativeTime(activity.created_at)}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
