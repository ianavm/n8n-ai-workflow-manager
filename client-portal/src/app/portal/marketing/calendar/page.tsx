"use client";

import { useEffect, useState, useMemo, useCallback } from "react";
import { ChevronLeft, ChevronRight, CalendarDays } from "lucide-react";

import { PlatformIcon } from "@/components/marketing/PlatformIcon";
import { PageHeader } from "@/components/portal/PageHeader";
import { Button } from "@/components/ui-shadcn/button";
import {
  startOfMonth,
  endOfMonth,
  startOfWeek,
  endOfWeek,
  eachDayOfInterval,
  format,
  isSameMonth,
  isToday,
  addMonths,
  subMonths,
} from "date-fns";

interface CalendarEntry {
  id: string;
  content_id: string;
  title: string;
  content_type: string;
  platform: string;
  scheduled_date: string;
  scheduled_time: string | null;
  status: string;
  post_url: string | null;
}

type ViewMode = "month" | "week";

const ENTRY_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  scheduled: { bg: "rgba(59,130,246,0.2)", text: "#60A5FA" },
  posted: { bg: "rgba(16,185,129,0.2)", text: "#34D399" },
  failed: { bg: "rgba(239,68,68,0.2)", text: "#F87171" },
  cancelled: { bg: "rgba(107,114,128,0.2)", text: "#9CA3AF" },
};

const WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

function getEntriesForDate(
  entries: CalendarEntry[],
  dateStr: string
): CalendarEntry[] {
  return entries.filter((e) => e.scheduled_date === dateStr);
}

function EntryPill({ entry }: { entry: CalendarEntry }) {
  const style =
    ENTRY_STATUS_COLORS[entry.status] ?? ENTRY_STATUS_COLORS.scheduled;
  return (
    <div
      className="flex items-center gap-1 px-1.5 py-0.5 rounded text-xs truncate cursor-default"
      style={{ background: style.bg, color: style.text }}
      title={`${entry.title} (${entry.platform}) - ${entry.status}`}
    >
      <PlatformIcon platform={entry.platform} size={14} />
      <span className="truncate">{entry.title}</span>
    </div>
  );
}

function MobileListView({
  days,
  entries,
  currentMonth,
}: {
  days: Date[];
  entries: CalendarEntry[];
  currentMonth: Date;
}) {
  const daysWithEntries = days
    .filter((day) => isSameMonth(day, currentMonth))
    .map((day) => {
      const dateStr = format(day, "yyyy-MM-dd");
      return { day, dateStr, dayEntries: getEntriesForDate(entries, dateStr) };
    })
    .filter((d) => d.dayEntries.length > 0);

  if (daysWithEntries.length === 0) {
    return (
      <div className="floating-card p-8 text-center">
        <div className="mx-auto w-12 h-12 rounded-full bg-[rgba(16,185,129,0.1)] flex items-center justify-center mb-4">
          <CalendarDays size={24} className="text-[#10B981]" />
        </div>
        <h3 className="text-white font-medium mb-2">No scheduled posts</h3>
        <p className="text-sm text-[#6B7280]">
          Nothing scheduled this month yet.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {daysWithEntries.map(({ day, dateStr, dayEntries }) => (
        <div key={dateStr} className="floating-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <span
              className={`text-sm font-medium ${
                isToday(day) ? "text-[#10B981]" : "text-white"
              }`}
            >
              {format(day, "EEE, d MMM")}
            </span>
            {isToday(day) && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#10B981]" />
            )}
          </div>
          <div className="space-y-2">
            {dayEntries.map((entry) => (
              <EntryPill key={entry.id} entry={entry} />
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(() => new Date());
  const [viewMode, setViewMode] = useState<ViewMode>("month");
  const [entries, setEntries] = useState<CalendarEntry[]>([]);
  const [loading, setLoading] = useState(true);

  // Compute visible day range based on current month
  const visibleDays = useMemo(() => {
    const monthStart = startOfMonth(currentMonth);
    const monthEnd = endOfMonth(currentMonth);
    const calendarStart = startOfWeek(monthStart, { weekStartsOn: 1 });
    const calendarEnd = endOfWeek(monthEnd, { weekStartsOn: 1 });
    return eachDayOfInterval({ start: calendarStart, end: calendarEnd });
  }, [currentMonth]);

  const rangeStart = useMemo(
    () => format(visibleDays[0], "yyyy-MM-dd"),
    [visibleDays]
  );
  const rangeEnd = useMemo(
    () => format(visibleDays[visibleDays.length - 1], "yyyy-MM-dd"),
    [visibleDays]
  );

  const fetchEntries = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(
        `/api/portal/marketing/calendar?start=${rangeStart}&end=${rangeEnd}`
      );
      if (res.ok) {
        const json = await res.json();
        setEntries(json.data ?? json ?? []);
      } else {
        setEntries([]);
      }
    } catch {
      setEntries([]);
    }
    setLoading(false);
  }, [rangeStart, rangeEnd]);

  useEffect(() => {
    fetchEntries();
  }, [fetchEntries]);

  const handlePrevMonth = () => setCurrentMonth((m) => subMonths(m, 1));
  const handleNextMonth = () => setCurrentMonth((m) => addMonths(m, 1));

  // Chunk days into weeks (rows of 7)
  const weeks = useMemo(() => {
    const result: Date[][] = [];
    for (let i = 0; i < visibleDays.length; i += 7) {
      result.push(visibleDays.slice(i, i + 7));
    }
    return result;
  }, [visibleDays]);

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Marketing"
        title="Content calendar"
        description="Plan and publish across every channel."
      />

      {/* Month nav + view toggle */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon-sm" onClick={handlePrevMonth} aria-label="Previous month">
            <ChevronLeft className="size-4" />
          </Button>
          <span className="text-lg font-semibold text-foreground min-w-[180px] text-center">
            {format(currentMonth, "MMMM yyyy")}
          </span>
          <Button variant="ghost" size="icon-sm" onClick={handleNextMonth} aria-label="Next month">
            <ChevronRight className="size-4" />
          </Button>
        </div>

        {/* View Toggle */}
        <div className="flex items-center gap-1 bg-[rgba(255,255,255,0.03)] rounded-lg p-1 border border-[rgba(255,255,255,0.06)]">
          <button
            onClick={() => setViewMode("month")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              viewMode === "month"
                ? "bg-[rgba(16,185,129,0.15)] text-[#10B981]"
                : "text-[#B0B8C8] hover:text-white"
            }`}
          >
            Month
          </button>
          <button
            onClick={() => setViewMode("week")}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
              viewMode === "week"
                ? "bg-[rgba(16,185,129,0.15)] text-[#10B981]"
                : "text-[#B0B8C8] hover:text-white"
            }`}
          >
            Week
          </button>
        </div>
      </div>

      {/* Loading */}
      {loading ? (
        <div className="floating-card p-12 text-center">
          <div className="animate-pulse space-y-4">
            <div className="h-4 w-32 mx-auto bg-[rgba(255,255,255,0.06)] rounded" />
            <div className="grid grid-cols-7 gap-2">
              {Array.from({ length: 35 }).map((_, i) => (
                <div
                  key={i}
                  className="h-20 bg-[rgba(255,255,255,0.03)] rounded"
                />
              ))}
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Desktop: Calendar Grid */}
          <div className="hidden md:block">
            <div className="floating-card overflow-hidden">
              {/* Weekday Header */}
              <div className="grid grid-cols-7 border-b border-[rgba(255,255,255,0.06)]">
                {WEEKDAY_LABELS.map((label) => (
                  <div
                    key={label}
                    className="px-2 py-3 text-center text-xs font-medium text-[#6B7280] uppercase tracking-wider"
                  >
                    {label}
                  </div>
                ))}
              </div>

              {/* Week Rows */}
              {weeks.map((week, weekIdx) => (
                <div
                  key={weekIdx}
                  className="grid grid-cols-7 border-b border-[rgba(255,255,255,0.03)] last:border-b-0"
                >
                  {week.map((day) => {
                    const dateStr = format(day, "yyyy-MM-dd");
                    const inMonth = isSameMonth(day, currentMonth);
                    const today = isToday(day);
                    const dayEntries = getEntriesForDate(entries, dateStr);

                    return (
                      <div
                        key={dateStr}
                        className={`min-h-[100px] p-2 border-r border-[rgba(255,255,255,0.03)] last:border-r-0 transition-colors ${
                          inMonth
                            ? "bg-transparent"
                            : "bg-[rgba(0,0,0,0.15)]"
                        }`}
                      >
                        {/* Date number */}
                        <div className="flex items-center gap-1.5 mb-1">
                          <span
                            className={`text-xs font-medium leading-none ${
                              today
                                ? "text-[#10B981]"
                                : inMonth
                                ? "text-[#B0B8C8]"
                                : "text-[#6B7280]/40"
                            }`}
                          >
                            {format(day, "d")}
                          </span>
                          {today && (
                            <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] flex-shrink-0" />
                          )}
                        </div>

                        {/* Entries */}
                        <div className="space-y-1">
                          {dayEntries.slice(0, 3).map((entry) => (
                            <EntryPill key={entry.id} entry={entry} />
                          ))}
                          {dayEntries.length > 3 && (
                            <span className="text-xs text-[#6B7280] pl-1">
                              +{dayEntries.length - 3} more
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>

            {/* Empty state for no entries */}
            {entries.length === 0 && (
              <div className="text-center py-8">
                <p className="text-sm text-[#6B7280]">
                  No scheduled posts this month. Schedule content to see it
                  here.
                </p>
              </div>
            )}
          </div>

          {/* Mobile: List View */}
          <div className="md:hidden">
            <MobileListView
              days={visibleDays}
              entries={entries}
              currentMonth={currentMonth}
            />
          </div>
        </>
      )}
    </div>
  );
}
