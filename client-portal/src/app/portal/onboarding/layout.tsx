import Link from "next/link";
import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";

import { BlobBackground } from "@/components/portal/BlobBackground";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[var(--bg-primary)]">
      <BlobBackground intensity="subtle" />
      <div className="relative z-[1]">
        <header className="flex items-center justify-between px-6 py-5 max-w-3xl mx-auto">
          <div className="flex items-center gap-2">
            <span className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)]">
              <ShieldCheck className="size-4 text-white" aria-hidden />
            </span>
            <span className="text-base font-bold tracking-[0.08em] text-foreground">
              ANYVISION
            </span>
          </div>
          <Link
            href="/portal/settings"
            className="text-sm text-[var(--text-dim)] hover:text-foreground transition-colors"
          >
            Save &amp; exit
          </Link>
        </header>

        <main className="max-w-2xl mx-auto px-4 pb-12">{children}</main>
      </div>
    </div>
  );
}
