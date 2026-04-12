"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { createClient } from "@/lib/supabase/client";

interface ThemeContextValue {
  brandColor: string;
  logoUrl: string | null;
  companyName: string;
  faviconUrl: string | null;
  isCustomBranded: boolean;
}

const DEFAULT_BRAND_COLOR = "#6366F1";

const ThemeContext = createContext<ThemeContextValue>({
  brandColor: DEFAULT_BRAND_COLOR,
  logoUrl: null,
  companyName: "ANYVISION",
  faviconUrl: null,
  isCustomBranded: false,
});

function hexToRgba(hex: string, alpha: number): string {
  const cleaned = hex.replace("#", "");
  const r = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const b = parseInt(cleaned.slice(4, 6), 16);
  if (isNaN(r) || isNaN(g) || isNaN(b)) return `rgba(99,102,241,${alpha})`;
  return `rgba(${r},${g},${b},${alpha})`;
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<ThemeContextValue>({
    brandColor: DEFAULT_BRAND_COLOR,
    logoUrl: null,
    companyName: "ANYVISION",
    faviconUrl: null,
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
          .select("company_name, logo_url, brand_color, favicon_url")
          .eq("auth_user_id", user.id)
          .maybeSingle();

        if (!client) return;

        const brandColor = client.brand_color || DEFAULT_BRAND_COLOR;
        const isCustom = brandColor !== DEFAULT_BRAND_COLOR;

        // Inject CSS variables for brand theming
        document.documentElement.style.setProperty("--brand-primary", brandColor);
        document.documentElement.style.setProperty("--brand-primary-glow", hexToRgba(brandColor, 0.12));
        document.documentElement.style.setProperty("--brand-primary-bg", hexToRgba(brandColor, 0.08));

        // Dynamic page title
        const companyName = client.company_name || "ANYVISION";
        document.title = `${companyName} Portal`;

        // Dynamic favicon
        if (client.favicon_url) {
          const link = document.querySelector<HTMLLinkElement>("link[rel='icon']");
          if (link) {
            link.href = client.favicon_url;
          } else {
            const newLink = document.createElement("link");
            newLink.rel = "icon";
            newLink.href = client.favicon_url;
            document.head.appendChild(newLink);
          }
        }

        setTheme({
          brandColor,
          logoUrl: client.logo_url || null,
          companyName,
          faviconUrl: client.favicon_url || null,
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
