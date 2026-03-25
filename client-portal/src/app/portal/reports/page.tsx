"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { DateRangePicker, type DateRange } from "@/components/ui/DateRangePicker";
import { exportToCSV, exportToPDF } from "@/lib/export";
import { subDays, format } from "date-fns";
import { toast } from "sonner";
import { Download, FileText } from "lucide-react";

function getDateRange(range: DateRange, customStart?: string, customEnd?: string) {
  const end = new Date();
  let start: Date;
  if (range === "7d") start = subDays(end, 7);
  else if (range === "30d") start = subDays(end, 30);
  else if (range === "90d") start = subDays(end, 90);
  else {
    start = customStart ? new Date(customStart) : subDays(end, 30);
    if (customEnd) end.setTime(new Date(customEnd).getTime());
  }
  return { start: start.toISOString(), end: end.toISOString() };
}

export default function ReportsPage() {
  const supabase = createClient();
  const [dateRange, setDateRange] = useState<DateRange>("30d");
  const [customStart, setCustomStart] = useState<string>();
  const [customEnd, setCustomEnd] = useState<string>();
  const [clientId, setClientId] = useState<string>();
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    async function init() {
      const {
        data: { user },
      } = await supabase.auth.getUser();
      if (!user) return;
      const { data: profile } = await supabase
        .from("clients")
        .select("id")
        .eq("auth_user_id", user.id)
        .single();
      if (profile) setClientId(profile.id);
    }
    init();
  }, [supabase]);

  async function handleExport(type: "csv" | "pdf") {
    if (!clientId) return;
    setExporting(true);

    const { start, end } = getDateRange(dateRange, customStart, customEnd);

    const { data: events } = await supabase
      .from("stat_events")
      .select("event_type, created_at, metadata")
      .eq("client_id", clientId)
      .gte("created_at", start)
      .lte("created_at", end)
      .order("created_at", { ascending: false });

    const rows = (events || []).map((e) => ({
      Type: e.event_type.replace(/_/g, " "),
      Date: format(new Date(e.created_at), "yyyy-MM-dd HH:mm:ss"),
      Details: JSON.stringify(e.metadata),
    }));

    const filename = `anyvision-report-${format(new Date(), "yyyy-MM-dd")}`;

    if (type === "csv") {
      await exportToCSV(rows, filename);
      toast.success("CSV exported successfully");
    } else {
      await exportToPDF(rows, filename, "AnyVision Media — Workflow Report");
      toast.success("PDF exported successfully");
    }

    setExporting(false);
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            Export <span className="gradient-text">Reports</span>
          </h1>
          <p className="text-base text-[#B0B8C8] mt-2">
            Download workflow data for the selected period
          </p>
        </div>
      </div>

      <Card>
        <h3 className="text-sm font-medium text-white mb-4">Date Range</h3>
        <DateRangePicker
          value={dateRange}
          onChange={(range, start, end) => {
            setDateRange(range);
            setCustomStart(start);
            setCustomEnd(end);
          }}
          customStart={customStart}
          customEnd={customEnd}
        />
      </Card>

      <Card>
        <h3 className="text-sm font-medium text-white mb-4">Download</h3>
        <p className="text-sm text-[#6B7280] mb-4">
          Export all workflow events for the selected date range.
        </p>
        <div className="flex gap-3">
          <Button
            onClick={() => handleExport("csv")}
            loading={exporting}
            variant="secondary"
          >
            <Download size={16} />
            Export CSV
          </Button>
          <Button
            onClick={() => handleExport("pdf")}
            loading={exporting}
            variant="secondary"
          >
            <FileText size={16} />
            Export PDF
          </Button>
        </div>
      </Card>
    </div>
  );
}
