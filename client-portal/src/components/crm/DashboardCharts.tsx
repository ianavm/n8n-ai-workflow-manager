"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { CardShell } from "./CardShell";

interface Props {
  dailyCreated: Array<{ day: string; count: number }>;
  byIndustry: Array<{ industry: string; count: number }>;
  byStage: Array<{ stage_key: string; label: string; color: string | null; count: number }>;
  winRate: number | null;
}

const INDUSTRY_COLORS = [
  "#FF6D5A",
  "#8B5CF6",
  "#38BDF8",
  "#2DD4BF",
  "#F59E0B",
  "#EC4899",
];

const tooltipStyle = {
  background: "#121827",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 8,
  fontSize: 12,
  color: "#F2F4F8",
};

export function DashboardCharts({
  dailyCreated,
  byIndustry,
  byStage,
  winRate,
}: Props) {
  return (
    <>
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <CardShell title="Leads Created (30d)" className="xl:col-span-2">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={dailyCreated} margin={{ top: 10, right: 12, bottom: 0, left: -20 }}>
                <defs>
                  <linearGradient id="leadsGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF6D5A" stopOpacity={0.45} />
                    <stop offset="100%" stopColor="#FF6D5A" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "#71717A" }}
                  tickFormatter={(v) => v.slice(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#71717A" }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip contentStyle={tooltipStyle} cursor={{ stroke: "#FF6D5A", strokeOpacity: 0.2 }} />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#FF6D5A"
                  strokeWidth={2}
                  fill="url(#leadsGrad)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardShell>

        <CardShell title="By Industry">
          <div className="h-64 flex items-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Tooltip contentStyle={tooltipStyle} />
                <Pie
                  data={byIndustry}
                  dataKey="count"
                  nameKey="industry"
                  innerRadius={55}
                  outerRadius={90}
                  paddingAngle={3}
                  stroke="none"
                >
                  {byIndustry.map((_, i) => (
                    <Cell key={i} fill={INDUSTRY_COLORS[i % INDUSTRY_COLORS.length]} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <ul className="mt-3 space-y-1">
            {byIndustry.map((row, i) => (
              <li key={row.industry} className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-2 text-[#B0B8C8]">
                  <span
                    className="w-2 h-2 rounded-full inline-block"
                    style={{ background: INDUSTRY_COLORS[i % INDUSTRY_COLORS.length] }}
                  />
                  {row.industry}
                </span>
                <span className="text-white font-medium tabular-nums">{row.count}</span>
              </li>
            ))}
          </ul>
        </CardShell>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <CardShell title="Pipeline by Stage" className="xl:col-span-2">
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={byStage}
                layout="vertical"
                margin={{ top: 5, right: 12, bottom: 0, left: 8 }}
              >
                <XAxis
                  type="number"
                  tick={{ fontSize: 10, fill: "#71717A" }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <YAxis
                  dataKey="label"
                  type="category"
                  tick={{ fontSize: 11, fill: "#B0B8C8" }}
                  width={110}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip contentStyle={tooltipStyle} cursor={{ fill: "rgba(255,109,90,0.08)" }} />
                <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                  {byStage.map((s, i) => (
                    <Cell key={i} fill={s.color ?? "#FF6D5A"} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </CardShell>

        <CardShell title="Win Rate">
          <div className="flex flex-col items-center justify-center h-64">
            <WinRateRing value={winRate} />
            <p className="mt-4 text-xs text-[#71717A] text-center max-w-[200px]">
              {winRate === null
                ? "No won or lost deals yet. Once deals close, your win rate appears here."
                : "Share of decided deals that closed won."}
            </p>
          </div>
        </CardShell>
      </div>
    </>
  );
}

function WinRateRing({ value }: { value: number | null }) {
  const pct = value ?? 0;
  const size = 140;
  const stroke = 12;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} role="img" aria-label="Win rate">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="rgba(255,255,255,0.06)"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke="#FF6D5A"
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={value === null ? c : offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[26px] font-semibold text-white tabular-nums">
          {value === null ? "—" : `${pct.toFixed(0)}%`}
        </span>
      </div>
    </div>
  );
}
