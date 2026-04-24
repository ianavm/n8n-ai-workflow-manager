"use client";

import { useEffect, useState } from "react";
import { format, subDays } from "date-fns";
import { Download, FileSpreadsheet, FileText } from "lucide-react";
import { toast } from "sonner";

import { createClient } from "@/lib/supabase/client";
import { exportToCSV, exportToPDF } from "@/lib/export";

import { PageHeader } from "@/components/portal/PageHeader";
import { DateRangePicker, type DateRange as UIRange } from "@/components/ui/DateRangePicker";

import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui-shadcn/card";

function getDateRange(range: UIRange, customStart?: string, customEnd?: string) {
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
  const [dateRange, setDateRange] = useState<UIRange>("30d");
  const [customStart, setCustomStart] = useState<string>();
  const [customEnd, setCustomEnd] = useState<string>();
  const [clientId, setClientId] = useState<string>();
  const [exporting, setExporting] = useState<"csv" | "pdf" | null>(null);

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
    setExporting(type);

    try {
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
    } catch {
      toast.error("Export failed. Please try again.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="flex flex-col gap-8 max-w-5xl">
      <PageHeader
        eyebrow="Reports"
        title="Export workflow reports"
        description="Download workflow data for any date range as CSV or PDF."
      />

      <Card variant="default" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Date range</CardTitle>
          <CardDescription>Select the period to include in your export.</CardDescription>
        </CardHeader>
        <CardContent className="pt-4">
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
        </CardContent>
      </Card>

      <Card variant="default" accent="gradient" padding="lg">
        <CardHeader>
          <CardTitle className="text-base">Download</CardTitle>
          <CardDescription>
            Export every workflow event in the selected range.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col sm:flex-row gap-3 pt-4">
          <Button
            onClick={() => handleExport("csv")}
            loading={exporting === "csv"}
            disabled={!clientId || Boolean(exporting)}
            variant="default"
          >
            <FileSpreadsheet className="size-4" />
            Export CSV
          </Button>
          <Button
            onClick={() => handleExport("pdf")}
            loading={exporting === "pdf"}
            disabled={!clientId || Boolean(exporting)}
            variant="outline"
          >
            <FileText className="size-4" />
            Export PDF
          </Button>
        </CardContent>
      </Card>

      <Card variant="default" padding="lg" className="text-[var(--text-muted)]">
        <div className="flex items-start gap-3">
          <span className="grid place-items-center size-10 rounded-full bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)] shrink-0">
            <Download className="size-4" aria-hidden />
          </span>
          <div className="flex-1">
            <p className="text-sm font-semibold text-foreground">What&rsquo;s included?</p>
            <p className="text-sm mt-1 leading-relaxed">
              Every workflow event logged during the selected period — lead captures, message
              sends, campaign updates, payments, and any workflow failures. Full metadata is
              included so the export works as an audit trail.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}
