"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import { ActivityTimeline } from "@/components/marketing/ActivityTimeline";
import { LeadScoreBadge } from "@/components/marketing/LeadScoreBadge";
import { AddActivityModal } from "@/components/marketing/AddActivityModal";
import {
  ArrowLeft,
  Mail,
  Phone,
  Building2,
  FileText,
  PhoneCall,
  RefreshCw,
  Loader2,
  ChevronDown,
} from "lucide-react";

interface Lead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: string;
  source_detail: string | null;
  score: number | null;
  stage: string;
  assigned_agent: string | null;
  tags: string[] | null;
  notes: string | null;
  conversion_value: number | null;
  lost_reason: string | null;
  campaign_id: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

interface Activity {
  id: string;
  activity_type: string;
  title: string;
  notes: string | null;
  actor: string;
  created_at: string;
  metadata: Record<string, unknown> | null;
}

const STAGES = [
  "new",
  "contacted",
  "qualified",
  "booked",
  "proposal",
  "won",
  "lost",
];

const STAGE_COLORS: Record<string, string> = {
  new: "#6B7280",
  contacted: "#3B82F6",
  qualified: "#F59E0B",
  booked: "#8B5CF6",
  proposal: "#D97706",
  won: "#10B981",
  lost: "#EF4444",
};

export default function LeadDetailPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();

  const [lead, setLead] = useState<Lead | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [activityPage, setActivityPage] = useState(1);
  const [hasMoreActivities, setHasMoreActivities] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);

  // Modal states
  const [showActivityModal, setShowActivityModal] = useState(false);
  const [showStageDropdown, setShowStageDropdown] = useState(false);

  const loadLead = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/portal/marketing/leads/${id}`);
      if (!res.ok) {
        router.push("/portal/marketing/leads");
        return;
      }
      const body = await res.json();
      setLead(body.lead);
      setActivities(body.activities ?? []);
      // If we got exactly 10 activities from the initial load, there may be more
      setHasMoreActivities((body.activities ?? []).length >= 10);
    } catch {
      router.push("/portal/marketing/leads");
    } finally {
      setLoading(false);
    }
  }, [id, router]);

  useEffect(() => {
    loadLead();
  }, [loadLead]);

  async function loadMoreActivities() {
    setLoadingMore(true);
    const nextPage = activityPage + 1;
    try {
      const res = await fetch(
        `/api/portal/marketing/leads/${id}/activities?page=${nextPage}&limit=20`
      );
      if (res.ok) {
        const body = await res.json();
        const newActivities = body.data ?? [];
        setActivities((prev) => [...prev, ...newActivities]);
        setActivityPage(nextPage);
        setHasMoreActivities(newActivities.length >= 20);
      }
    } finally {
      setLoadingMore(false);
    }
  }

  async function handleStageChange(newStage: string) {
    if (!lead || lead.stage === newStage) {
      setShowStageDropdown(false);
      return;
    }

    // Optimistic update
    const prevStage = lead.stage;
    setLead({ ...lead, stage: newStage });
    setShowStageDropdown(false);

    try {
      const res = await fetch(`/api/portal/marketing/leads/${id}/stage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: newStage }),
      });

      if (!res.ok) {
        setLead((prev) => (prev ? { ...prev, stage: prevStage } : prev));
        return;
      }

      // Reload activities to show the stage_change entry
      loadLead();
    } catch {
      setLead((prev) => (prev ? { ...prev, stage: prevStage } : prev));
    }
  }

  function handleActivityAdded() {
    setShowActivityModal(false);
    loadLead();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-[#10B981]" />
      </div>
    );
  }

  if (!lead) {
    return (
      <div className="text-center py-20 text-[#6B7280]">Lead not found</div>
    );
  }

  const displayName = [lead.first_name, lead.last_name].filter(Boolean).join(" ") || "Unknown";
  const stageColor = STAGE_COLORS[lead.stage] ?? "#6B7280";

  const utmParams = lead.metadata
    ? Object.entries(lead.metadata).filter(([k]) => k.startsWith("utm_"))
    : [];

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={() => router.push("/portal/marketing/leads")}
        className="flex items-center gap-2 text-sm text-[#B0B8C8] hover:text-white transition-colors"
      >
        <ArrowLeft size={16} />
        Back to Pipeline
      </button>

      {/* Lead Header */}
      <div className="floating-card p-6">
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{displayName}</h1>
              {lead.score != null && <LeadScoreBadge score={lead.score} />}
            </div>

            <div className="flex items-center gap-4 flex-wrap text-sm text-[#B0B8C8]">
              {lead.email && (
                <span className="flex items-center gap-1.5">
                  <Mail size={14} className="text-[#6B7280]" />
                  {lead.email}
                </span>
              )}
              {lead.phone && (
                <span className="flex items-center gap-1.5">
                  <Phone size={14} className="text-[#6B7280]" />
                  {lead.phone}
                </span>
              )}
              {lead.company && (
                <span className="flex items-center gap-1.5">
                  <Building2 size={14} className="text-[#6B7280]" />
                  {lead.company}
                </span>
              )}
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              {/* Source badge */}
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium text-[#3B82F6] bg-[rgba(59,130,246,0.15)]">
                {lead.source.replace(/_/g, " ")}
              </span>

              {/* Stage badge with dropdown */}
              <div className="relative">
                <button
                  onClick={() => setShowStageDropdown(!showStageDropdown)}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium transition-colors"
                  style={{
                    color: stageColor,
                    backgroundColor: `${stageColor}26`,
                  }}
                >
                  {lead.stage}
                  <ChevronDown size={12} />
                </button>

                {showStageDropdown && (
                  <div
                    className="absolute top-full left-0 mt-1 py-1 rounded-lg border z-20 min-w-[120px]"
                    style={{
                      background: "rgba(17,24,39,0.95)",
                      borderColor: "rgba(255,255,255,0.08)",
                      backdropFilter: "blur(20px)",
                    }}
                  >
                    {STAGES.map((s) => (
                      <button
                        key={s}
                        onClick={() => handleStageChange(s)}
                        className={`w-full text-left px-3 py-1.5 text-xs transition-colors ${
                          s === lead.stage
                            ? "text-white bg-[rgba(255,255,255,0.05)]"
                            : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
                        }`}
                      >
                        <span
                          className="inline-block w-1.5 h-1.5 rounded-full mr-2"
                          style={{ backgroundColor: STAGE_COLORS[s] }}
                        />
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {lead.tags?.map((tag) => (
                <span
                  key={tag}
                  className="inline-block px-2 py-0.5 rounded text-xs text-[#B0B8C8] bg-[rgba(255,255,255,0.05)]"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>

          <div className="text-xs text-[#6B7280] text-right">
            <p>
              Created{" "}
              {new Date(lead.created_at).toLocaleDateString("en-ZA", {
                day: "numeric",
                month: "short",
                year: "numeric",
              })}
            </p>
            {lead.assigned_agent && (
              <p className="mt-1">Assigned to {lead.assigned_agent}</p>
            )}
            {lead.conversion_value != null && lead.conversion_value > 0 && (
              <p className="mt-1 text-[#10B981] font-medium">
                Value: R{(lead.conversion_value / 100).toLocaleString("en-ZA")}
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Info + Quick Actions */}
        <div className="lg:col-span-1 space-y-6">
          {/* Quick Actions */}
          <div className="floating-card p-4">
            <h3 className="text-sm font-medium text-white mb-3">Quick Actions</h3>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => setShowActivityModal(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(255,255,255,0.06)]"
              >
                <FileText size={14} />
                Add Note
              </button>
              <button
                onClick={() => setShowActivityModal(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(255,255,255,0.06)]"
              >
                <PhoneCall size={14} />
                Log Call
              </button>
              <button
                onClick={() => setShowActivityModal(true)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(255,255,255,0.06)]"
              >
                <Mail size={14} />
                Send Email
              </button>
              <button
                onClick={() => setShowStageDropdown(!showStageDropdown)}
                className="flex items-center gap-2 px-3 py-2 rounded-lg text-xs text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)] transition-colors border border-[rgba(255,255,255,0.06)]"
              >
                <RefreshCw size={14} />
                Change Stage
              </button>
            </div>
          </div>

          {/* Notes */}
          {lead.notes && (
            <div className="floating-card p-4">
              <h3 className="text-sm font-medium text-white mb-2">Notes</h3>
              <p className="text-xs text-[#B0B8C8] whitespace-pre-wrap">
                {lead.notes}
              </p>
            </div>
          )}

          {/* Lost reason */}
          {lead.stage === "lost" && lead.lost_reason && (
            <div className="floating-card p-4 border-l-2 border-red-500">
              <h3 className="text-sm font-medium text-red-400 mb-2">
                Lost Reason
              </h3>
              <p className="text-xs text-[#B0B8C8]">{lead.lost_reason}</p>
            </div>
          )}

          {/* UTM Params */}
          {utmParams.length > 0 && (
            <div className="floating-card p-4">
              <h3 className="text-sm font-medium text-white mb-2">
                Tracking Parameters
              </h3>
              <div className="space-y-1.5">
                {utmParams.map(([key, value]) => (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-xs text-[#6B7280]">
                      {key.replace("utm_", "")}
                    </span>
                    <span className="text-xs text-[#B0B8C8]">
                      {String(value)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Lead Details */}
          <div className="floating-card p-4">
            <h3 className="text-sm font-medium text-white mb-3">Details</h3>
            <dl className="space-y-2 text-xs">
              {lead.source_detail && (
                <div className="flex justify-between">
                  <dt className="text-[#6B7280]">Source Detail</dt>
                  <dd className="text-[#B0B8C8]">{lead.source_detail}</dd>
                </div>
              )}
              {lead.campaign_id && (
                <div className="flex justify-between">
                  <dt className="text-[#6B7280]">Campaign</dt>
                  <dd className="text-[#B0B8C8] truncate max-w-[160px]">
                    {lead.campaign_id}
                  </dd>
                </div>
              )}
              <div className="flex justify-between">
                <dt className="text-[#6B7280]">Lead ID</dt>
                <dd className="text-[#B0B8C8] font-mono truncate max-w-[160px]">
                  {lead.id}
                </dd>
              </div>
            </dl>
          </div>
        </div>

        {/* Right: Activity Timeline */}
        <div className="lg:col-span-2">
          <div className="floating-card p-5">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-white">Activity</h3>
              <button
                onClick={() => setShowActivityModal(true)}
                className="text-xs text-[#10B981] hover:text-[#059669] transition-colors"
              >
                + Add Activity
              </button>
            </div>

            <ActivityTimeline activities={activities} />

            {hasMoreActivities && (
              <div className="text-center mt-4">
                <button
                  onClick={loadMoreActivities}
                  disabled={loadingMore}
                  className="text-xs text-[#10B981] hover:text-[#059669] transition-colors disabled:opacity-50"
                >
                  {loadingMore ? "Loading..." : "Load more activities"}
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Activity Modal */}
      {showActivityModal && (
        <AddActivityModal
          leadId={id}
          onClose={() => setShowActivityModal(false)}
          onAdded={handleActivityAdded}
        />
      )}
    </div>
  );
}
