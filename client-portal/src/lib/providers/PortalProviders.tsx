"use client";

import type { ReactNode } from "react";
import { ColorSchemeProvider } from "./ColorSchemeProvider";
import { BrandProvider } from "./BrandProvider";
import { MemberProvider } from "./MemberProvider";

// Toaster lives at the root layout (components/ThemedToaster.tsx) so both
// admin and portal zones share one instance. Do not mount another here.
export function PortalProviders({ children }: { children: ReactNode }) {
  return (
    <ColorSchemeProvider>
      <BrandProvider>
        <MemberProvider>{children}</MemberProvider>
      </BrandProvider>
    </ColorSchemeProvider>
  );
}
