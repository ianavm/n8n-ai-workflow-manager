"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { createClient } from "@/lib/supabase/client";

export interface BrandContextValue {
  brandColor: string;
  logoUrl: string | null;
  companyName: string;
  faviconUrl: string | null;
  isCustomBranded: boolean;
}

const DEFAULT_BRAND_COLOR = "#FF6D5A"; // AVM coral — matches --accent-coral token
const DEFAULT_COMPANY_NAME = "ANYVISION";

const DEFAULT_VALUE: BrandContextValue = {
  brandColor: DEFAULT_BRAND_COLOR,
  logoUrl: null,
  companyName: DEFAULT_COMPANY_NAME,
  faviconUrl: null,
  isCustomBranded: false,
};

const BrandContext = createContext<BrandContextValue>(DEFAULT_VALUE);

function hexToRgba(hex: string, alpha: number): string {
  const cleaned = hex.replace("#", "");
  const r = parseInt(cleaned.slice(0, 2), 16);
  const g = parseInt(cleaned.slice(2, 4), 16);
  const b = parseInt(cleaned.slice(4, 6), 16);
  if (Number.isNaN(r) || Number.isNaN(g) || Number.isNaN(b)) {
    return `rgba(255,109,90,${alpha})`;
  }
  return `rgba(${r},${g},${b},${alpha})`;
}

// When a client sets a custom brand color we override the PRIMARY token only.
// AVM's purple + teal secondary accents intentionally remain unchanged.
function applyBrandVars(brandColor: string): void {
  const root = document.documentElement;
  const glow = hexToRgba(brandColor, 0.3);
  const gradient = `linear-gradient(135deg, ${brandColor}, ${brandColor})`;

  root.style.setProperty("--brand-primary", brandColor);
  root.style.setProperty("--brand-glow", glow);
  root.style.setProperty("--brand-gradient", gradient);
  // shadcn aliases reference --brand-primary via CSS cascade, but we also
  // override directly for primitives that don't re-read on runtime changes.
  root.style.setProperty("--primary", brandColor);
  root.style.setProperty("--ring", brandColor);
  root.style.setProperty("--glow-coral", glow);
}

function clearBrandVars(): void {
  const root = document.documentElement;
  root.style.removeProperty("--brand-primary");
  root.style.removeProperty("--brand-glow");
  root.style.removeProperty("--brand-gradient");
  root.style.removeProperty("--primary");
  root.style.removeProperty("--ring");
  root.style.removeProperty("--glow-coral");
}

export function BrandProvider({ children }: { children: ReactNode }) {
  const [brand, setBrand] = useState<BrandContextValue>(DEFAULT_VALUE);

  useEffect(() => {
    let cancelled = false;

    async function loadBranding() {
      try {
        const supabase = createClient();
        const { data: auth } = await supabase.auth.getUser();
        if (!auth.user) return;

        const { data: client } = await supabase
          .from("clients")
          .select("company_name, logo_url, brand_color, favicon_url")
          .eq("auth_user_id", auth.user.id)
          .maybeSingle();

        if (cancelled || !client) return;

        const brandColor = client.brand_color || DEFAULT_BRAND_COLOR;
        const companyName = client.company_name || DEFAULT_COMPANY_NAME;
        const isCustom = brandColor !== DEFAULT_BRAND_COLOR;

        // Apply CSS vars only if the client has a custom brand color.
        // Otherwise leave the :root defaults untouched.
        if (isCustom) {
          applyBrandVars(brandColor);
        }

        document.title = `${companyName} Portal`;

        if (client.favicon_url) {
          const existing = document.querySelector<HTMLLinkElement>("link[rel='icon']");
          if (existing) {
            existing.href = client.favicon_url;
          } else {
            const link = document.createElement("link");
            link.rel = "icon";
            link.href = client.favicon_url;
            document.head.appendChild(link);
          }
        }

        setBrand({
          brandColor,
          logoUrl: client.logo_url || null,
          companyName,
          faviconUrl: client.favicon_url || null,
          isCustomBranded: isCustom || Boolean(client.logo_url),
        });
      } catch {
        // Fail silently — defaults remain.
      }
    }

    loadBranding();

    return () => {
      cancelled = true;
      clearBrandVars();
    };
  }, []);

  return <BrandContext.Provider value={brand}>{children}</BrandContext.Provider>;
}

export function useBrand(): BrandContextValue {
  return useContext(BrandContext);
}
