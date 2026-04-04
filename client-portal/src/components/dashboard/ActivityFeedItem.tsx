"use client";

import { motion } from "framer-motion";
import { formatDistanceToNow } from "date-fns";
import {
  UserPlus,
  Send,
  MessageCircle,
  AlertTriangle,
  DollarSign,
  FileText,
  Target,
  FileEdit,
  Activity,
  type LucideIcon,
} from "lucide-react";

interface ActivityFeedItemProps {
  type: string;
  message: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
  index: number;
}

interface IconConfig {
  icon: LucideIcon;
  color: string;
  bg: string;
}

const ICON_MAP: Record<string, IconConfig> = {
  lead_created: {
    icon: UserPlus,
    color: "#10B981",
    bg: "rgba(16,185,129,0.15)",
  },
  message_sent: {
    icon: Send,
    color: "#6C63FF",
    bg: "rgba(108,99,255,0.15)",
  },
  message_received: {
    icon: MessageCircle,
    color: "#3B82F6",
    bg: "rgba(59,130,246,0.15)",
  },
  workflow_crash: {
    icon: AlertTriangle,
    color: "#EF4444",
    bg: "rgba(239,68,68,0.15)",
  },
  payment: {
    icon: DollarSign,
    color: "#00D4AA",
    bg: "rgba(0,212,170,0.15)",
  },
  invoice: {
    icon: FileText,
    color: "#00D4AA",
    bg: "rgba(0,212,170,0.15)",
  },
  campaign: {
    icon: Target,
    color: "#FF6D5A",
    bg: "rgba(255,109,90,0.15)",
  },
  content: {
    icon: FileEdit,
    color: "#6C63FF",
    bg: "rgba(108,99,255,0.15)",
  },
};

const DEFAULT_CONFIG: IconConfig = {
  icon: Activity,
  color: "#6C63FF",
  bg: "rgba(108,99,255,0.15)",
};

const BORDER_COLORS: Record<string, string> = {
  lead_created: "#10B981",
  message_sent: "#6C63FF",
  message_received: "#3B82F6",
  workflow_crash: "#EF4444",
  payment: "#00D4AA",
  invoice: "#00D4AA",
  campaign: "#FF6D5A",
  content: "#6C63FF",
};

export function ActivityFeedItem({
  type,
  message,
  timestamp,
  index,
}: ActivityFeedItemProps) {
  const config = ICON_MAP[type] ?? DEFAULT_CONFIG;
  const IconComponent = config.icon;
  const borderColor = BORDER_COLORS[type] ?? "#6C63FF";

  let relativeTime: string;
  try {
    relativeTime = formatDistanceToNow(new Date(timestamp), {
      addSuffix: true,
    });
  } catch {
    relativeTime = timestamp;
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{
        delay: index * 0.05,
        duration: 0.3,
        ease: [0.16, 1, 0.3, 1],
      }}
      style={{
        display: "flex",
        alignItems: "flex-start",
        gap: "12px",
        padding: "12px 14px",
        borderLeft: `2px solid ${borderColor}`,
        borderRadius: "0 8px 8px 0",
        background: "rgba(255,255,255,0.02)",
        transition: "background 0.2s ease",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.background =
          "rgba(255,255,255,0.04)";
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.background =
          "rgba(255,255,255,0.02)";
      }}
    >
      {/* Icon */}
      <div
        style={{
          width: "32px",
          height: "32px",
          borderRadius: "50%",
          background: config.bg,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}
      >
        <IconComponent size={16} color={config.color} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontSize: "14px",
            color: "#B0B8C8",
            lineHeight: 1.4,
            margin: 0,
          }}
        >
          {message}
        </p>
        <span
          style={{
            fontSize: "12px",
            color: "#6B7280",
            marginTop: "2px",
            display: "block",
          }}
        >
          {relativeTime}
        </span>
      </div>
    </motion.div>
  );
}
