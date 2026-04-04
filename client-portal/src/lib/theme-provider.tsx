"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createClient } from "@/lib/supabase/client";

interface ThemeContextValue {
  brandColor: string;
  logoUrl: string | null;
  companyName: string;
  isCustomBranded: boolean;
}

const DEFAULT_BRAND_COLOR = "#6C63FF";

const ThemeContext = createContext<ThemeContextValue>({
  brandColor: DEFAULT_BRAND_COLOR,
  logoUrl: null,
  companyName: "ANYVISION",
  isCustomBranded: false,
});

function hexToRgba(hex: string, alpha: number): string {
  const cleaned = hex.replace("#", "");
  const r = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const b = parseInt(cleaned.slice(4, 6), 16);
  if (isNaN(r) || isNaN(g) || isNaN(b)) return `rgba(108,99,255,${alpha})`;
  return `rgba(${r},${g},${b},${alpha})`;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeContextValue>({
    brandColor: DEFAULT_BRAND_COLOR,
    logoUrl: null,
    companyName: "ANYVISION",
    isCustomBranded: false,
  });

  useEffect(() => {
    async function loadBranding() {
      try {
        const supabase = createClient();
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        const { data: client } = await supabase
          .from("clients")
          .select("company_name, logo_url, brand_color")
          .eq("auth_user_id", user.id)
          .maybeSingle();

        if (!client) return;

        const brandColor = client.brand_color || DEFAULT_BRAND_COLOR;
        const isCustom = brandColor !== DEFAULT_BRAND_COLOR;

        if (isCustom) {
          document.documentElement.style.setProperty("--brand-primary", brandColor);
          document.documentElement.style.setProperty("--brand-primary-glow", hexToRgba(brandColor, 0.3));
          document.documentElement.style.setProperty("--brand-primary-bg", hexToRgba(brandColor, 0.1));
        }

        setTheme({
          brandColor,
          logoUrl: client.logo_url || null,
          companyName: client.company_name || "ANYVISION",
          isCustomBranded: isCustom || !!client.logo_url,
        });
      } catch {
        // Fail silently — use defaults
      }
    }

    loadBranding();

    return () => {
      document.documentElement.style.removeProperty("--brand-primary");
      document.documentElement.style.removeProperty("--brand-primary-glow");
      document.documentElement.style.removeProperty("--brand-primary-bg");
    };
  }, []);

  return (
    <ThemeContext.Provider value={theme}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
