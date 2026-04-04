"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import { Plus, Sparkles } from "lucide-react";

interface ContentItem {
  id: string;
  title: string;
  content_type: string;
  status: string;
  body: string | null;
  hook: string | null;
  hashtags: string[] | null;
  target_platforms: string[] | null;
  campaign_id: string | null;
  ai_generated: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

type ContentStatus =
  | "all"
  | "idea"
  | "draft"
  | "in_review"
  | "approved"
  | "scheduled"
  | "posted"
  | "failed"
  | "archived";

const STATUS_TABS: { value: ContentStatus; label: string }[] = [
  { value: "all", label: "All" },
  { value: "idea", label: "Ideas" },
  { value: "draft", label: "Drafts" },
  { value: "in_review", label: "In Review" },
  { value: "approved", label: "Approved" },
  { value: "scheduled", label: "Scheduled" },
  { value: "posted", label: "Posted" },
];

const STATUS_BADGE_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  idea: { bg: "rgba(107,114,128,0.15)", text: "#9CA3AF", label: "Idea" },
  draft: { bg: "rgba(59,130,246,0.15)", text: "#3B82F6", label: "Draft" },
  in_review: { bg: "rgba(234,179,8,0.15)", text: "#EAB308", label: "In Review" },
  approved: { bg: "rgba(16,185,129,0.15)", text: "#10B981", label: "Approved" },
  scheduled: { bg: "rgba(139,92,246,0.15)", text: "#8B5CF6", label: "Scheduled" },
  posted: { bg: "rgba(20,184,166,0.15)", text: "#14B8A6", label: "Posted" },
  failed: { bg: "rgba(239,68,68,0.15)", text: "#EF4444", label: "Failed" },
  archived: { bg: "rgba(107,114,128,0.1)", text: "#6B7280", label: "Archived" },
};

const CONTENT_TYPE_STYLES: Record<string, { bg: string; text: string }> = {
  post: { bg: "rgba(59,130,246,0.12)", text: "#60A5FA" },
  reel: { bg: "rgba(236,72,153,0.12)", text: "#F472B6" },
  story: { bg: "rgba(249,115,22,0.12)", text: "#FB923C" },
  video_script: { bg: "rgba(139,92,246,0.12)", text: "#A78BFA" },
  blog: { bg: "rgba(16,185,129,0.12)", text: "#34D399" },
  newsletter: { bg: "rgba(234,179,8,0.12)", text: "#FBBF24" },
  ad_copy: { bg: "rgba(239,68,68,0.12)", text: "#F87171" },
  idea: { bg: "rgba(107,114,128,0.12)", text: "#9CA3AF" },
};

function formatContentType(type: string): string {
  return type
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_BADGE_STYLES[status] ?? STATUS_BADGE_STYLES.idea;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium"
      style={{ background: style.bg, color: style.text }}
    >
      {style.label}
    </span>
  );
}

function ContentTypeBadge({ type }: { type: string }) {
  const style = CONTENT_TYPE_STYLES[type] ?? CONTENT_TYPE_STYLES.idea;
  return (
    <span
      className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
      style={{ background: style.bg, color: style.text }}
    >
      {formatContentType(type)}
    </span>
  );
}

function PlaceholderCard() {
  return (
    <div className="floating-card p-5 animate-pulse">
      <div className="flex items-center justify-between mb-3">
        <div className="h-4 w-24 bg-[rgba(255,255,255,0.06)] rounded" />
        <div className="h-5 w-16 bg-[rgba(255,255,255,0.06)] rounded-full" />
      </div>
      <div className="h-3 w-full bg-[rgba(255,255,255,0.04)] rounded mb-2" />
      <div className="h-3 w-2/3 bg-[rgba(255,255,255,0.04)] rounded mb-4" />
      <div className="flex items-center gap-2">
        <div className="h-5 w-5 bg-[rgba(255,255,255,0.06)] rounded" />
        <div className="h-5 w-5 bg-[rgba(255,255,255,0.06)] rounded" />
      </div>
    </div>
  );
}

export default function ContentPage() {
  const supabase = createClient();
  const [content, setContent] = useState<ContentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<ContentStatus>("all");

  const loadContent = useCallback(async () => {
    setLoading(true);

    let query = supabase
      .from("mkt_content")
      .select("*")
      .order("created_at", { ascending: false });

    if (activeTab !== "all") {
      query = query.eq("status", activeTab);
    }

    const { data } = await query;
    setContent(data ?? []);
    setLoading(false);
  }, [supabase, activeTab]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Content</h1>
          <p className="text-sm text-[#B0B8C8] mt-1">
            {loading ? "Loading..." : `${content.length} items`}
          </p>
        </div>
        <button
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium text-white transition-all hover:opacity-90"
          style={{
            background: "linear-gradient(135deg, #10B981, #059669)",
          }}
        >
          <Plus size={16} />
          New Content
        </button>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1 scrollbar-hide">
        {STATUS_TABS.map((tab) => {
          const isActive = activeTab === tab.value;
          return (
            <button
              key={tab.value}
              onClick={() => setActiveTab(tab.value)}
              className={`px-3.5 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-all ${
                isActive
                  ? "bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.3)]"
                  : "text-[#B0B8C8] bg-[rgba(255,255,255,0.03)] border border-transparent hover:bg-[rgba(255,255,255,0.05)] hover:text-white"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <PlaceholderCard key={i} />
          ))}
        </div>
      ) : content.length === 0 ? (
        <div className="floating-card p-12 text-center">
          <div className="mx-auto w-12 h-12 rounded-full bg-[rgba(16,185,129,0.1)] flex items-center justify-center mb-4">
            <Plus size={24} className="text-[#10B981]" />
          </div>
          <h3 className="text-white font-medium mb-2">No content items yet</h3>
          <p className="text-sm text-[#6B7280] max-w-sm mx-auto">
            Start by creating your first piece of content.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {content.map((item) => (
            <button
              key={item.id}
              onClick={() => {
                // TODO: open content detail modal
                console.log(item.title);
              }}
              className="floating-card p-5 text-left transition-all hover:bg-[rgba(255,255,255,0.05)] hover:border-[rgba(16,185,129,0.2)] cursor-pointer"
            >
              {/* Top row: type badge + status badge */}
              <div className="flex items-center justify-between mb-3">
                <ContentTypeBadge type={item.content_type} />
                <div className="flex items-center gap-2">
                  {item.ai_generated && (
                    <span
                      className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium"
                      style={{
                        background: "rgba(139,92,246,0.15)",
                        color: "#A78BFA",
                      }}
                    >
                      <Sparkles size={10} />
                      AI
                    </span>
                  )}
                  <StatusBadge status={item.status} />
                </div>
              </div>

              {/* Title */}
              <h3 className="text-white font-medium text-sm mb-2 line-clamp-1">
                {item.title}
              </h3>

              {/* Body preview */}
              {item.body && (
                <p className="text-[#B0B8C8] text-xs leading-relaxed mb-3 line-clamp-2">
                  {item.body}
                </p>
              )}

              {/* Footer: platforms + date */}
              <div className="flex items-center justify-between mt-auto pt-2 border-t border-[rgba(255,255,255,0.04)]">
                <div className="flex items-center gap-1">
                  {item.target_platforms && item.target_platforms.length > 0 ? (
                    item.target_platforms.map((platform) => (
                      <PlatformIcon
                        key={platform}
                        platform={platform}
                        size={20}
                      />
                    ))
                  ) : (
                    <span className="text-xs text-[#6B7280]">No platforms</span>
                  )}
                </div>
                <span className="text-xs text-[#6B7280]">
                  {new Date(item.created_at).toLocaleDateString("en-ZA")}
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
