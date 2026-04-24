"use client";

import { useChartTheme } from "@/lib/charts/useChartTheme";

/**
 * Reusable Recharts `<defs>` block — drop inside any Recharts chart
 * (AreaChart, BarChart, LineChart, etc.) to get brand-aware gradient
 * fills. Reference as `fill="url(#avm-fill-coral)"`.
 */
export function GradientDefs() {
  const theme = useChartTheme();
  return (
    <defs>
      <linearGradient id="avm-fill-purple" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stopColor={theme.colors.purple} stopOpacity={0.3} />
        <stop offset="100%" stopColor={theme.colors.purple} stopOpacity={0} />
      </linearGradient>
      <linearGradient id="avm-fill-teal" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stopColor={theme.colors.teal} stopOpacity={0.3} />
        <stop offset="100%" stopColor={theme.colors.teal} stopOpacity={0} />
      </linearGradient>
      <linearGradient id="avm-fill-coral" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stopColor={theme.colors.coral} stopOpacity={0.3} />
        <stop offset="100%" stopColor={theme.colors.coral} stopOpacity={0} />
      </linearGradient>
      <linearGradient id="avm-fill-brand" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stopColor={theme.colors.brand} stopOpacity={0.3} />
        <stop offset="100%" stopColor={theme.colors.brand} stopOpacity={0} />
      </linearGradient>
      <linearGradient id="avm-fill-danger" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%"  stopColor={theme.colors.danger} stopOpacity={0.3} />
        <stop offset="100%" stopColor={theme.colors.danger} stopOpacity={0} />
      </linearGradient>
      <linearGradient id="avm-grad-main" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"   stopColor={theme.colors.purple} />
        <stop offset="100%" stopColor={theme.colors.teal} />
      </linearGradient>
      <linearGradient id="avm-grad-coral" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%"   stopColor={theme.colors.coral} />
        <stop offset="100%" stopColor="#FF8F7A" />
      </linearGradient>
    </defs>
  );
}
