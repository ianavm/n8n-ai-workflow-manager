"use client";

import { useEffect, useState } from "react";
import { Toaster } from "sonner";

// Root-level Toaster — lives outside PortalProviders so admin pages
// (which don't wrap their tree in ColorSchemeProvider) still get toasts.
// Observes the <html> class list to react to theme toggles from the
// portal ThemeToggle without needing React context.
export function ThemedToaster() {
  const [scheme, setScheme] = useState<"light" | "dark">("dark");

  useEffect(() => {
    const root = document.documentElement;
    const read = (): "light" | "dark" => (root.classList.contains("light") ? "light" : "dark");
    setScheme(read());

    const observer = new MutationObserver(() => setScheme(read()));
    observer.observe(root, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, []);

  return (
    <Toaster
      theme={scheme}
      position="bottom-right"
      toastOptions={{
        style: {
          background: "var(--bg-elevated)",
          border: "1px solid var(--border-subtle)",
          color: "var(--text-white)",
          backdropFilter: "blur(20px)",
        },
        className: "font-sans",
      }}
    />
  );
}
