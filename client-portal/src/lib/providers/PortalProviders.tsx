"use client";

import type { ReactNode } from "react";
import { ColorSchemeProvider } from "./ColorSchemeProvider";
import { BrandProvider } from "./BrandProvider";

// Toaster lives at the root layout (components/ThemedToaster.tsx) so both
// admin and portal zones share one instance. Do not mount another here.
export function PortalProviders({ children }: { children: ReactNode }) {
  return (
    <ColorSchemeProvider>
      <BrandProvider>{children}</BrandProvider>
    </ColorSchemeProvider>
  );
}
