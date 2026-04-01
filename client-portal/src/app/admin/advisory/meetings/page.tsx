"use client";

import { useEffect, useState, useCallback } from "react";
import { Badge } from "@/components/ui/Badge";
import { Calendar, Video, MapPin, Clock } from "lucide-react";
import { format } from "date-fns";

interface FAMeeting {
  id: string;
  meeting_type: string;
  status: string;
  scheduled_at: string;
  duration_minutes: number;
  location_type: string | null;
  teams_meeting_url: string | null;
  title: string | null;
  client: {
    id: string;
    first_name: string;
    last_name: string;
    email: string;
  } | null;
  adviser: { id: string; full_name: string } | null;
}

const MEETING_STATUSES = [
  "scheduled",
  "confirmed",
  "in_progress",
  "completed",
  "cancelled",
];

const statusVariant = (
  s: string
): "default" | "success" | "warning" | "danger" | "purple" => {
  switch (s) {
    case "scheduled":
      return "default";
    case "confirmed":
      return "purple";
    case "in_progress":
      return "warning";
    case "completed":
      return "success";
    case "cancelled":
      return "danger";
    default:
      return "default";
  }
};

const typeLabel = (t: string): string =>
  t
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");

export default function MeetingsPage() {
  const [meetings, setMeetings] = useState<FAMeeting[]>([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  const fetchMeetings = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    if (statusFilter) params.set("status", statusFilter);

    const res = await fetch(`/api/advisory/meetings?${params.toString()}`);
    if (res.ok) {
      const json = await res.json();
      setMeetings(json.data ?? []);
    }
    setLoading(false);
  }, [statusFilter]);

  useEffect(() => {
    fetchMeetings();
  }, [fetchMeetings]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#00A651] border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Advisory <span className="gradient-text">Meetings</span>
          </h1>
          <p className="text-sm text-[#B0B8C8] mt-2">
            {meetings.length} meetings
          </p>
        </div>
      </div>

      {/* Status Filter */}
      <div className="filter-pills">
        <button
          className={`filter-pill ${statusFilter === "" ? "active" : ""}`}
          onClick={() => setStatusFilter("")}
        >
          All
        </button>
        {MEETING_STATUSES.map((s) => (
          <button
            key={s}
            className={`filter-pill ${statusFilter === s ? "active" : ""}`}
            onClick={() => setStatusFilter(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1).replace("_", " ")}
          </button>
        ))}
      </div>

      {/* Meetings List */}
      {meetings.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Calendar
            size={32}
            className="text-[#6B7280] mx-auto mb-3 opacity-50"
          />
          <p className="text-sm text-[#6B7280]">No meetings found</p>
        </div>
      ) : (
        <div className="space-y-3">
          {meetings.map((m) => (
            <div
              key={m.id}
              className="glass-card p-4 hover:border-[rgba(108,99,255,0.3)] transition-colors cursor-pointer"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  {/* Date badge */}
                  <div className="w-14 h-14 rounded-lg bg-[rgba(108,99,255,0.1)] border border-[rgba(108,99,255,0.2)] flex flex-col items-center justify-center flex-shrink-0">
                    <span className="text-xs text-[#00A651] font-medium">
                      {format(new Date(m.scheduled_at), "MMM")}
                    </span>
                    <span className="text-lg font-bold text-white leading-tight">
                      {format(new Date(m.scheduled_at), "dd")}
                    </span>
                  </div>

                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-sm font-semibold text-white">
                        {m.client
                          ? `${m.client.first_name} ${m.client.last_name}`
                          : "Unknown client"}
                      </span>
                      <Badge variant={statusVariant(m.status)}>
                        {m.status.replace("_", " ")}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-4 text-xs text-[#6B7280]">
                      <span className="flex items-center gap-1">
                        <Calendar size={12} />
                        {typeLabel(m.meeting_type)}
                      </span>
                      <span className="flex items-center gap-1">
                        <Clock size={12} />
                        {format(new Date(m.scheduled_at), "HH:mm")} (
                        {m.duration_minutes}min)
                      </span>
                      {m.teams_meeting_url && (
                        <span className="flex items-center gap-1 text-[#00A651]">
                          <Video size={12} />
                          Video
                        </span>
                      )}
                      {m.location_type && (
                        <span className="flex items-center gap-1">
                          <MapPin size={12} />
                          {m.location_type}
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <span className="text-xs text-[#6B7280]">
                    {m.adviser?.full_name ?? "Unassigned"}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
