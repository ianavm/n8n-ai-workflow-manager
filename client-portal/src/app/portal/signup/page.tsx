import Link from "next/link";
import { ArrowRight, Lock, ShieldCheck } from "lucide-react";

import { BlobBackground } from "@/components/portal/BlobBackground";
import { Card } from "@/components/ui-shadcn/card";
import { Button } from "@/components/ui-shadcn/button";

export default function SignupPage() {
  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center px-4 py-12 overflow-hidden">
      <BlobBackground intensity="hero" />
      <div className="relative z-[1] w-full max-w-[440px] flex flex-col items-center">
        <Card variant="default" accent="gradient-static" padding="lg" className="w-full animate-fade-in-up">
          <div className="flex items-center gap-2 mb-6">
            <span className="grid place-items-center size-9 rounded-[var(--radius-sm)] bg-[image:var(--brand-gradient)] shadow-[0_0_20px_var(--brand-glow)] text-white font-bold">
              A
            </span>
            <span className="text-base font-bold tracking-[0.08em] text-foreground">
              ANYVISION
            </span>
          </div>

          <h1 className="text-xl font-bold text-foreground">Signups are closed</h1>
          <p className="text-sm text-[var(--text-muted)] leading-relaxed mt-3 mb-6">
            The AnyVision portal is currently invite-only while we onboard new clients
            directly. To request access, email{" "}
            <a
              href="mailto:ian@anyvisionmedia.com?subject=Portal access request"
              className="font-medium text-[var(--brand-primary)] hover:underline"
            >
              ian@anyvisionmedia.com
            </a>
            .
          </p>

          <div className="flex flex-col gap-3">
            <Button asChild variant="default" size="lg" className="w-full">
              <Link href="/portal/login">
                I already have an account
                <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="lg" className="w-full">
              <a href="https://www.anyvisionmedia.com">Back to anyvisionmedia.com</a>
            </Button>
          </div>
        </Card>

        <div className="flex items-center justify-center gap-6 mt-8 text-xs text-[var(--text-dim)]">
          <span className="inline-flex items-center gap-1.5">
            <Lock className="size-3.5" />
            256-bit encrypted
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck className="size-3.5" />
            POPIA compliant
          </span>
        </div>
      </div>
    </div>
  );
}
