"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend,
  LineChart,
  Line,
  BarChart,
  Bar,
} from "recharts";

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

function shortDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-ZA", { day: "numeric", month: "short" });
}

const PLATFORM_COLORS: Record<string, string> = {
  google_ads: "#4285F4",
  meta_ads: "#0668E1",
  tiktok_ads: "#FF0050",
  linkedin_ads: "#0A66C2",
  multi_platform: "#10B981",
};

const METRIC_COLORS: Record<string, string> = {
  clicks: "#10B981",
  conversions: "#6C63FF",
  leads_generated: "#F59E0B",
  impressions: "#0668E1",
};

const DARK_AXIS = { fill: "#B0B8C8", fontSize: 12 };
const DARK_GRID = { stroke: "rgba(255,255,255,0.06)" };

/* ------------------------------------------------------------------ */
/* Tooltip Wrappers                                                    */
/* ------------------------------------------------------------------ */

interface TooltipPayload {
  name?: string;
  value?: number;
  color?: string;
  payload?: Record<string, unknown>;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayload[];
  label?: string;
  isCurrency?: boolean;
}

function DarkTooltip({ active, payload, label, isCurrency = false }: CustomTooltipProps) {
  if (!active || !payload?.length) return null;

  return (
    <div className="rounded-lg border border-[rgba(255,255,255,0.1)] bg-[#1A1D23] px-3 py-2 shadow-lg">
      <p className="text-xs text-[#6B7280] mb-1">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} className="text-sm font-medium" style={{ color: entry.color ?? "#fff" }}>
          {entry.name}: {isCurrency ? formatZAR(entry.value ?? 0) : (entry.value ?? 0).toLocaleString()}
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 1. SpendTrendChart                                                  */
/* ------------------------------------------------------------------ */

interface SpendTrendProps {
  data: ReadonlyArray<{ date: string; spend: number }>;
}

export function SpendTrendChart({ data }: SpendTrendProps) {
  const formatted = data.map((d) => ({ ...d, label: shortDate(d.date) }));

  return (
    <div className="floating-card p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Daily Ad Spend</h3>
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={formatted} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <defs>
            <linearGradient id="spendGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#10B981" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#10B981" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" {...DARK_GRID} />
          <XAxis dataKey="label" tick={DARK_AXIS} axisLine={false} tickLine={false} />
          <YAxis
            tick={DARK_AXIS}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => formatZAR(v)}
          />
          <Tooltip content={<DarkTooltip isCurrency />} />
          <Area
            type="monotone"
            dataKey="spend"
            stroke="#10B981"
            strokeWidth={2}
            fill="url(#spendGradient)"
            name="Spend"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 2. PlatformBreakdownPie                                             */
/* ------------------------------------------------------------------ */

interface PlatformPieProps {
  data: ReadonlyArray<{ platform: string; spend: number }>;
}

function platformLabel(p: string): string {
  const labels: Record<string, string> = {
    google_ads: "Google",
    meta_ads: "Meta",
    tiktok_ads: "TikTok",
    linkedin_ads: "LinkedIn",
    multi_platform: "Multi",
  };
  return labels[p] ?? p;
}

interface CustomLegendPayload {
  value?: string;
  color?: string;
}

function CustomPieLegend({ payload }: { payload?: CustomLegendPayload[] }) {
  if (!payload) return null;
  return (
    <div className="flex flex-wrap justify-center gap-4 mt-2">
      {payload.map((entry, i) => (
        <span key={i} className="flex items-center gap-1.5 text-xs text-[#B0B8C8]">
          <span
            className="inline-block w-2.5 h-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {entry.value}
        </span>
      ))}
    </div>
  );
}

export function PlatformBreakdownPie({ data }: PlatformPieProps) {
  const pieData = data.map((d) => ({
    name: platformLabel(d.platform),
    value: d.spend,
    color: PLATFORM_COLORS[d.platform] ?? "#6B7280",
  }));

  return (
    <div className="floating-card p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Spend by Platform</h3>
      <ResponsiveContainer width="100%" height={300}>
        <PieChart>
          <Pie
            data={pieData}
            cx="50%"
            cy="45%"
            innerRadius={60}
            outerRadius={100}
            paddingAngle={3}
            dataKey="value"
            nameKey="name"
            stroke="none"
          >
            {pieData.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            content={<DarkTooltip isCurrency />}
          />
          <Legend content={<CustomPieLegend />} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 3. MetricsTrendChart                                                */
/* ------------------------------------------------------------------ */

interface MetricsTrendProps {
  data: ReadonlyArray<{
    date: string;
    clicks: number;
    conversions: number;
    leads_generated: number;
  }>;
  metrics?: ReadonlyArray<"clicks" | "conversions" | "leads_generated">;
}

export function MetricsTrendChart({
  data,
  metrics = ["clicks", "conversions", "leads_generated"],
}: MetricsTrendProps) {
  const formatted = data.map((d) => ({ ...d, label: shortDate(d.date) }));

  const metricLabels: Record<string, string> = {
    clicks: "Clicks",
    conversions: "Conversions",
    leads_generated: "Leads",
  };

  return (
    <div className="floating-card p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Performance Trends</h3>
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={formatted} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" {...DARK_GRID} />
          <XAxis dataKey="label" tick={DARK_AXIS} axisLine={false} tickLine={false} />
          <YAxis tick={DARK_AXIS} axisLine={false} tickLine={false} />
          <Tooltip content={<DarkTooltip />} />
          {metrics.map((metric) => (
            <Line
              key={metric}
              type="monotone"
              dataKey={metric}
              stroke={METRIC_COLORS[metric]}
              strokeWidth={2}
              dot={false}
              name={metricLabels[metric] ?? metric}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* 4. CampaignBarChart                                                 */
/* ------------------------------------------------------------------ */

interface CampaignBarProps {
  data: ReadonlyArray<{ name: string; spend: number }>;
}

export function CampaignBarChart({ data }: CampaignBarProps) {
  return (
    <div className="floating-card p-5">
      <h3 className="text-sm font-semibold text-white mb-4">Top Campaigns by Spend</h3>
      <ResponsiveContainer width="100%" height={300}>
        <BarChart
          data={[...data]}
          layout="vertical"
          margin={{ top: 5, right: 20, left: 10, bottom: 5 }}
        >
          <CartesianGrid strokeDasharray="3 3" horizontal={false} {...DARK_GRID} />
          <XAxis
            type="number"
            tick={DARK_AXIS}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => formatZAR(v)}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ ...DARK_AXIS, width: 120 }}
            axisLine={false}
            tickLine={false}
            width={130}
          />
          <Tooltip content={<DarkTooltip isCurrency />} />
          <Bar dataKey="spend" fill="#10B981" radius={[0, 4, 4, 0]} name="Spend" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
