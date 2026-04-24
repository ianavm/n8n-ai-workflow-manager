"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ColorScheme = "dark" | "light";

interface ColorSchemeContextValue {
  scheme: ColorScheme;
  setScheme: (scheme: ColorScheme) => void;
  toggle: () => void;
}

const STORAGE_KEY = "portal-theme";

const ColorSchemeContext = createContext<ColorSchemeContextValue>({
  scheme: "dark",
  setScheme: () => {},
  toggle: () => {},
});

function applyScheme(scheme: ColorScheme): void {
  const root = document.documentElement;
  if (scheme === "light") {
    root.classList.add("light");
  } else {
    root.classList.remove("light");
  }
  root.style.colorScheme = scheme;
}

function readInitialScheme(): ColorScheme {
  if (typeof window === "undefined") return "dark";
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark") return stored;
  } catch {
    /* localStorage unavailable (SSR / private mode) */
  }
  const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
  return prefersDark ? "dark" : "light";
}

export function ColorSchemeProvider({ children }: { children: ReactNode }) {
  // Stay "dark" during SSR; hydrate from localStorage + media query on mount.
  // The pre-hydration <script> in app/layout.tsx applies the class before
  // React mounts, so there's no flash of the wrong theme.
  const [scheme, setSchemeState] = useState<ColorScheme>("dark");

  useEffect(() => {
    const initial = readInitialScheme();
    setSchemeState(initial);
    applyScheme(initial);
  }, []);

  const setScheme = useCallback((next: ColorScheme) => {
    setSchemeState(next);
    applyScheme(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
  }, []);

  const toggle = useCallback(() => {
    setScheme(scheme === "dark" ? "light" : "dark");
  }, [scheme, setScheme]);

  const value = useMemo<ColorSchemeContextValue>(
    () => ({ scheme, setScheme, toggle }),
    [scheme, setScheme, toggle],
  );

  return <ColorSchemeContext.Provider value={value}>{children}</ColorSchemeContext.Provider>;
}

export function useColorScheme(): ColorSchemeContextValue {
  return useContext(ColorSchemeContext);
}
