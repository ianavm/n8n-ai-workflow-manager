import type { ReactNode } from "react";

export default function OnboardingLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen" style={{ background: "#0A0F1C" }}>
      {/* Minimal header: logo + save & exit */}
      <header className="flex items-center justify-between px-6 py-4 max-w-3xl mx-auto">
        <div className="flex items-center gap-2">
          <svg viewBox="0 0 200 200" width="28" height="28" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <linearGradient id="obGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="#6C63FF" />
                <stop offset="100%" stopColor="#00D4AA" />
              </linearGradient>
            </defs>
            <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="url(#obGrad)" opacity="0.10" />
            <path d="M16,100 Q100,2 184,100 Q100,198 16,100 Z" fill="none" stroke="url(#obGrad)" strokeWidth="8" strokeLinejoin="round" />
            <circle cx="100" cy="100" r="16" fill="#0A0F1C" />
            <circle cx="100" cy="100" r="16" fill="none" stroke="url(#obGrad)" strokeWidth="2" opacity="0.4" />
            <circle cx="91" cy="91" r="5" fill="rgba(255,255,255,0.85)" />
          </svg>
          <span className="text-base font-semibold text-white">
            AnyVision<span className="text-[#FF6D5A]">.</span>
          </span>
        </div>
        <a
          href="/portal/settings"
          className="text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
        >
          Save &amp; exit
        </a>
      </header>

      <main className="max-w-2xl mx-auto px-4 pb-12">{children}</main>
    </div>
  );
}
