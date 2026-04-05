"use client";

import { Check, AlertTriangle, ExternalLink } from "lucide-react";

interface ConnectionCardProps {
  provider: {
    id: string;
    name: string;
    icon: string;
    color: string;
    description: string;
    docsUrl: string;
  };
  status: "not_connected" | "pending" | "connected" | "expired" | "error";
  accountName?: string | null;
  connectedAt?: string | null;
  lastError?: string | null;
}

export function ConnectionCard({ provider, status, accountName, lastError }: ConnectionCardProps) {
  const statusConfig = {
    not_connected: { label: "Not Connected", color: "#6B7280", bg: "rgba(107,114,128,0.1)" },
    pending: { label: "Pending", color: "#F59E0B", bg: "rgba(245,158,11,0.1)" },
    connected: { label: "Connected", color: "#00D4AA", bg: "rgba(0,212,170,0.1)" },
    expired: { label: "Expired", color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
    error: { label: "Error", color: "#EF4444", bg: "rgba(239,68,68,0.1)" },
  };

  const cfg = statusConfig[status];

  return (
    <div className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.03] hover:bg-white/[0.05] transition-all">
      <div className="flex items-start gap-3">
        {/* Provider icon */}
        <div
          className="w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-base"
          style={{ background: `${provider.color}20`, border: `1px solid ${provider.color}40` }}
        >
          {provider.icon}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium text-white">{provider.name}</h3>
            {/* Status badge */}
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium"
              style={{ color: cfg.color, background: cfg.bg }}
            >
              {status === "connected" && <Check size={10} />}
              {(status === "error" || status === "expired") && <AlertTriangle size={10} />}
              {cfg.label}
            </span>
          </div>
          <p className="text-xs text-[#6B7280] mt-0.5">{provider.description}</p>

          {/* Connected account name */}
          {status === "connected" && accountName && (
            <p className="text-xs text-[#00D4AA] mt-1">
              {accountName}
            </p>
          )}

          {/* Error message */}
          {status === "error" && lastError && (
            <p className="text-xs text-red-400 mt-1">{lastError}</p>
          )}
        </div>

        {/* Action button */}
        <div className="flex-shrink-0">
          {status === "not_connected" && (
            <button
              disabled
              title="Contact support@anyvisionmedia.com to connect this tool"
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#B0B8C8] transition-all cursor-help opacity-70"
              style={{ background: "rgba(255,255,255,0.08)", border: "1px solid rgba(255,255,255,0.12)" }}
            >
              Connect
            </button>
          )}
          {status === "connected" && (
            <a
              href={provider.docsUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 px-2.5 py-1.5 rounded-lg text-xs text-[#6B7280] hover:text-[#B0B8C8] hover:bg-white/[0.05] transition-all"
            >
              <ExternalLink size={12} />
              Manage
            </a>
          )}
          {(status === "error" || status === "expired") && (
            <button
              disabled
              title="Contact support@anyvisionmedia.com to reconnect"
              className="px-3 py-1.5 rounded-lg text-xs font-medium text-[#F59E0B] bg-[#F59E0B]/10 border border-[#F59E0B]/20 cursor-help opacity-70 transition-all"
            >
              Reconnect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
