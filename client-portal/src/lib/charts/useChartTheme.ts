"use client";

import { useEffect, useState } from "react";

import { getChartTheme, type ChartTheme } from "@/lib/charts/theme";

/**
 * Re-reads chart tokens whenever:
 *   - `<html class="light">` is toggled (ColorSchemeProvider),
 *   - `document.documentElement.style` is mutated (BrandProvider setting
 *     `--brand-primary` etc.).
 * Recharts re-renders naturally when its parent component receives new
 * props, so returning a fresh theme object is enough.
 */
export function useChartTheme(): ChartTheme {
  const [theme, setTheme] = useState<ChartTheme>(() => getChartTheme());

  useEffect(() => {
    // Hydrate on mount (SSR returns fallback).
    setTheme(getChartTheme());

    const refresh = () => setTheme(getChartTheme());

    const observer = new MutationObserver(refresh);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style"],
    });

    return () => observer.disconnect();
  }, []);

  return theme;
}
