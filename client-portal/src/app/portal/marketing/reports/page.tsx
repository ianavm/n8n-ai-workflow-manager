"use client";

import { useState, useEffect, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  SpendTrendChart,
  PlatformBreakdownPie,
  MetricsTrendChart,
  CampaignBarChart,
} from "@/components/marketing/ReportCharts";
import { ReportTable, formatZAR, formatNumber, formatPercent } from "@/components/marketing/ReportTable";
import type { ColumnDef } from "@/components/marketing/ReportTable";
import {
  BarChart3,
  Download,
  FileSpreadsheet,
  Loader2,
} from "lucide-react";

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

interface DailyMetrics {
  date: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
  leads_generated: number;
}

interface PlatformBreakdown {
  platform: string;
  impressions: number;
  clicks: number;
  spend: number;
  conversions: number;
}

interface TopCampaign {
  campaign_id: string;
  name: string;
  spend: number;
}

interface ReportData {
  report_type: string;
  date_range: { start_date: string; end_date: string };
  time_series: DailyMetrics[];
  totals: DailyMetrics;
  platform_breakdown?: PlatformBreakdown[];
  top_campaigns?: TopCampaign[];
  campaign_name?: string;
}

interface CampaignOption {
  id: string;
  name: string;
}

type ReportType = "overview" | "campaign" | "platform" | "attribution";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function todayStr(): string {
  return new Date().toISOString().slice(0, 10);
}

function firstOfMonth(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-01`;
}

function computeCTR(clicks: number, impressions: number): number {
  return impressions > 0 ? (clicks / impressions) * 100 : 0;
}

function computeCPC(spend: number, clicks: number): number {
  return clicks > 0 ? spend / clicks : 0;
}

function computeCPL(spend: number, leads: number): number {
  return leads > 0 ? spend / leads : 0;
}

/* ------------------------------------------------------------------ */
/* Export Helpers                                                       */
/* ------------------------------------------------------------------ */

function exportCSV(report: ReportData): void {
  const rows = report.time_series.map((row) => ({
    Date: row.date,
    Impressions: row.impressions,
    Clicks: row.clicks,
    Spend_ZAR: (row.spend / 100).toFixed(2),
    Conversions: row.conversions,
    Leads: row.leads_generated,
    CTR: computeCTR(row.clicks, row.impressions).toFixed(2) + "%",
    CPC_ZAR: (computeCPC(row.spend, row.clicks) / 100).toFixed(2),
    CPL_ZAR: (computeCPL(row.spend, row.leads_generated) / 100).toFixed(2),
  }));

  if (rows.length === 0) return;

  const headers = Object.keys(rows[0]);
  const csvLines = [
    headers.join(","),
    ...rows.map((r) =>
      headers.map((h) => String(r[h as keyof typeof r])).join(",")
    ),
  ];

  const blob = new Blob([csvLines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `performance_report_${report.date_range.start_date}_${report.date_range.end_date}.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

async function exportPDF(report: ReportData): Promise<void> {
  const { default: jsPDF } = await import("jspdf");
  await import("jspdf-autotable");

  const doc = new jsPDF({ orientation: "landscape" });

  // Title
  doc.setFontSize(18);
  doc.setTextColor(16, 185, 129);
  doc.text("Performance Report", 14, 20);

  // Date range
  doc.setFontSize(10);
  doc.setTextColor(100, 100, 100);
  doc.text(
    `Period: ${report.date_range.start_date} to ${report.date_range.end_date}`,
    14,
    28
  );
  doc.text(`Report type: ${report.report_type}`, 14, 34);
  doc.text(`Generated: ${new Date().toLocaleString("en-ZA")}`, 14, 40);

  // KPI Summary
  const t = report.totals;
  doc.setFontSize(12);
  doc.setTextColor(0, 0, 0);
  doc.text("Key Metrics", 14, 52);

  doc.setFontSize(10);
  doc.setTextColor(60, 60, 60);
  const kpiLines = [
    `Total Spend: R${(t.spend / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`,
    `Total Clicks: ${t.clicks.toLocaleString()}`,
    `Total Conversions: ${t.conversions.toLocaleString()}`,
    `Total Leads: ${t.leads_generated.toLocaleString()}`,
    `CTR: ${computeCTR(t.clicks, t.impressions).toFixed(2)}%`,
  ];
  kpiLines.forEach((line, i) => doc.text(line, 14, 60 + i * 6));

  // Data table
  const tableHead = [
    ["Date", "Impressions", "Clicks", "Spend (ZAR)", "Conversions", "Leads", "CTR", "CPC", "CPL"],
  ];
  const tableBody = report.time_series.map((row) => [
    row.date,
    row.impressions.toLocaleString(),
    row.clicks.toLocaleString(),
    `R${(row.spend / 100).toFixed(0)}`,
    row.conversions.toLocaleString(),
    row.leads_generated.toLocaleString(),
    computeCTR(row.clicks, row.impressions).toFixed(2) + "%",
    `R${(computeCPC(row.spend, row.clicks) / 100).toFixed(2)}`,
    `R${(computeCPL(row.spend, row.leads_generated) / 100).toFixed(2)}`,
  ]);

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  (doc as any).autoTable({
    startY: 94,
    head: tableHead,
    body: tableBody,
    theme: "grid",
    headStyles: { fillColor: [16, 185, 129], textColor: 255, fontSize: 8 },
    bodyStyles: { fontSize: 7, textColor: 50 },
    alternateRowStyles: { fillColor: [245, 247, 250] },
    margin: { left: 14, right: 14 },
  });

  doc.save(
    `performance_report_${report.date_range.start_date}_${report.date_range.end_date}.pdf`
  );
}

/* ------------------------------------------------------------------ */
/* Table Columns                                                       */
/* ------------------------------------------------------------------ */

const TABLE_COLUMNS: ColumnDef[] = [
  { key: "date", label: "Date", format: "date" },
  { key: "impressions", label: "Impressions", format: "number" },
  { key: "clicks", label: "Clicks", format: "number" },
  { key: "spend", label: "Spend", format: "zar" },
  { key: "conversions", label: "Conversions", format: "number" },
  { key: "leads_generated", label: "Leads", format: "number" },
  { key: "ctr", label: "CTR", format: "percent" },
  { key: "cpc", label: "CPC", format: "zar" },
  { key: "cpl", label: "CPL", format: "zar" },
];

/* ------------------------------------------------------------------ */
/* Page Component                                                      */
/* ------------------------------------------------------------------ */

const REPORT_TYPES: { value: ReportType; label: string }[] = [
  { value: "overview", label: "Overview" },
  { value: "campaign", label: "Campaign Deep-Dive" },
  { value: "platform", label: "Platform Comparison" },
  { value: "attribution", label: "Attribution" },
];

export default function ReportsPage() {
  const supabase = createClient();

  // Controls
  const [startDate, setStartDate] = useState(firstOfMonth);
  const [endDate, setEndDate] = useState(todayStr);
  const [reportType, setReportType] = useState<ReportType>("overview");
  const [campaignId, setCampaignId] = useState("");
  const [campaigns, setCampaigns] = useState<CampaignOption[]>([]);

  // Data
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pdfLoading, setPdfLoading] = useState(false);

  // Load campaign options
  useEffect(() => {
    async function loadCampaigns() {
      const { data } = await supabase
        .from("mkt_campaigns")
        .select("id, name")
        .order("name", { ascending: true });
      setCampaigns((data ?? []) as CampaignOption[]);
    }
    loadCampaigns();
  }, [supabase]);

  const generateReport = useCallback(async () => {
    setLoading(true);
    setError(null);
    setReport(null);

    const params = new URLSearchParams({
      start_date: startDate,
      end_date: endDate,
      report_type: reportType,
    });
    if (campaignId) params.set("campaign_id", campaignId);

    try {
      const res = await fetch(`/api/portal/marketing/reports?${params}`);
      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: "Request failed" }));
        setError(body.error ?? `Request failed (${res.status})`);
        return;
      }
      const data: ReportData = await res.json();
      setReport(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unexpected error");
    } finally {
      setLoading(false);
    }
  }, [startDate, endDate, reportType, campaignId]);

  // Enrich time series with computed metrics for the table
  const enrichedData = report?.time_series.map((row) => ({
    ...row,
    ctr: computeCTR(row.clicks, row.impressions),
    cpc: computeCPC(row.spend, row.clicks),
    cpl: computeCPL(row.spend, row.leads_generated),
  })) ?? [];

  const totals = report?.totals;

  const handleExportPDF = useCallback(async () => {
    if (!report) return;
    setPdfLoading(true);
    try {
      await exportPDF(report);
    } finally {
      setPdfLoading(false);
    }
  }, [report]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white">Performance Reports</h1>
        <p className="text-sm text-[#B0B8C8] mt-1">
          Analyze campaign performance across platforms and time periods
        </p>
      </div>

      {/* Controls */}
      <div className="floating-card p-5">
        <div className="flex flex-wrap items-end gap-4">
          {/* Start date */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#6B7280]">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981]"
            />
          </div>

          {/* End date */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#6B7280]">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981]"
            />
          </div>

          {/* Report Type */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-[#6B7280]">Report Type</label>
            <select
              value={reportType}
              onChange={(e) => setReportType(e.target.value as ReportType)}
              className="px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981]"
            >
              {REPORT_TYPES.map((rt) => (
                <option key={rt.value} value={rt.value}>
                  {rt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Campaign selector (shown only for campaign type) */}
          {reportType === "campaign" && (
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-medium text-[#6B7280]">Campaign</label>
              <select
                value={campaignId}
                onChange={(e) => setCampaignId(e.target.value)}
                className="px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8] focus:outline-none focus:border-[#10B981] min-w-[200px]"
              >
                <option value="">Select a campaign</option>
                {campaigns.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Generate button */}
          <button
            onClick={generateReport}
            disabled={loading || (reportType === "campaign" && !campaignId)}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            style={{
              background: "linear-gradient(135deg, #10B981, #059669)",
            }}
          >
            {loading ? (
              <Loader2 size={16} className="animate-spin" />
            ) : (
              <BarChart3 size={16} />
            )}
            Generate Report
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="floating-card p-4 border-l-4 border-red-500">
          <p className="text-sm text-red-400">{error}</p>
        </div>
      )}

      {/* Report content */}
      {report && totals && (
        <>
          {/* KPI Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <KPICard label="Total Spend" value={formatZAR(totals.spend)} />
            <KPICard label="Total Clicks" value={formatNumber(totals.clicks)} />
            <KPICard label="Conversions" value={formatNumber(totals.conversions)} />
            <KPICard label="Leads" value={formatNumber(totals.leads_generated)} />
            <KPICard
              label="CTR"
              value={formatPercent(computeCTR(totals.clicks, totals.impressions))}
            />
            <KPICard
              label="ROAS"
              value={
                totals.spend > 0
                  ? `${((totals.conversions * 100) / (totals.spend / 100)).toFixed(1)}x`
                  : "0x"
              }
            />
          </div>

          {/* Charts */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <SpendTrendChart data={report.time_series} />
            {report.platform_breakdown && report.platform_breakdown.length > 0 ? (
              <PlatformBreakdownPie data={report.platform_breakdown} />
            ) : (
              <MetricsTrendChart data={report.time_series} metrics={["clicks", "conversions", "leads_generated"]} />
            )}
            <MetricsTrendChart
              data={report.time_series}
              metrics={["clicks", "conversions", "leads_generated"]}
            />
            {report.top_campaigns && report.top_campaigns.length > 0 && (
              <CampaignBarChart data={report.top_campaigns} />
            )}
          </div>

          {/* Detail Table */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-white">Detailed Metrics</h2>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => exportCSV(report)}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-[#B0B8C8] bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] hover:text-white hover:border-[#10B981] transition-all"
                >
                  <FileSpreadsheet size={16} />
                  Export CSV
                </button>
                <button
                  onClick={handleExportPDF}
                  disabled={pdfLoading}
                  className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-[#B0B8C8] bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] hover:text-white hover:border-[#10B981] transition-all disabled:opacity-50"
                >
                  {pdfLoading ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Download size={16} />
                  )}
                  Export PDF
                </button>
              </div>
            </div>
            <ReportTable data={enrichedData} columns={TABLE_COLUMNS} />
          </div>
        </>
      )}

      {/* Empty state when no report generated yet */}
      {!report && !loading && !error && (
        <div className="floating-card p-12 text-center">
          <BarChart3 size={48} className="mx-auto text-[#333] mb-4" />
          <p className="text-[#6B7280] text-sm">
            Select a date range and report type, then click Generate Report.
          </p>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* KPI Card                                                            */
/* ------------------------------------------------------------------ */

function KPICard({ label, value }: { label: string; value: string }) {
  return (
    <div className="floating-card p-4">
      <p className="text-xs text-[#6B7280] mb-1">{label}</p>
      <p className="text-xl font-bold text-white">{value}</p>
    </div>
  );
}
