"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Check, ArrowRight, Sparkles } from "lucide-react";

interface Achievement {
  key: string;
  label: string;
  description: string;
  achieved: boolean;
  achieved_at: string | null;
  cta_label?: string;
  cta_href?: string;
}

interface AchievementsData {
  achievements: Achievement[];
  total: number;
  achieved: number;
  progress_pct: number;
}

interface TrialProgressProps {
  trialEnd: string | null;
  subscriptionStatus: string | null;
}

export function TrialProgress({ trialEnd, subscriptionStatus }: TrialProgressProps) {
  const [data, setData] = useState<AchievementsData | null>(null);
  const [dismissed, setDismissed] = useState(false);

  const isTrial = subscriptionStatus === "trialing";

  useEffect(() => {
    if (!isTrial) return;
    // Check dismissal in localStorage
    const key = "avm_trial_progress_dismissed";
    if (typeof window !== "undefined" && localStorage.getItem(key) === "true") {
      setDismissed(true);
      return;
    }

    async function load() {
      try {
        const res = await fetch("/api/portal/achievements");
        if (res.ok) setData(await res.json());
      } catch { /* silent */ }
    }
    load();
  }, [isTrial]);

  if (!isTrial || dismissed || !data) return null;

  // Calculate days remaining
  const daysRemaining = trialEnd
    ? Math.max(0, Math.ceil((new Date(trialEnd).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))
    : 30;

  const allDone = data.achieved >= data.total;

  return (
    <div className="floating-card p-5 border border-white/[0.08] bg-white/[0.03] rounded-2xl relative overflow-hidden">
      {/* Subtle gradient accent */}
      <div
        className="absolute top-0 left-0 right-0 h-1 rounded-t-2xl"
        style={{
          background: `linear-gradient(90deg, #6C63FF ${data.progress_pct}%, rgba(255,255,255,0.06) ${data.progress_pct}%)`,
        }}
      />

      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-white flex items-center gap-2">
            <Sparkles size={14} className="text-[#F59E0B]" />
            {allDone ? "Setup Complete!" : "Getting Started"}
          </h3>
          <p className="text-xs text-[#6B7280] mt-0.5">
            {allDone
              ? "You've completed all setup steps. Your automations are running."
              : `${data.achieved} of ${data.total} steps complete`}
            {" "}
            &middot; {daysRemaining} days left in trial
          </p>
        </div>
        <button
          onClick={() => {
            setDismissed(true);
            localStorage.setItem("avm_trial_progress_dismissed", "true");
          }}
          className="text-xs text-[#4B5563] hover:text-[#6B7280] transition-colors"
        >
          Dismiss
        </button>
      </div>

      {/* Achievement checklist */}
      <div className="space-y-1.5">
        {data.achievements.map((ach) => (
          <div
            key={ach.key}
            className={`flex items-center gap-3 px-3 py-2 rounded-xl transition-all ${
              ach.achieved
                ? "bg-transparent"
                : "bg-white/[0.02] hover:bg-white/[0.04]"
            }`}
          >
            {/* Checkbox */}
            <div
              className={`w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 transition-all ${
                ach.achieved
                  ? "bg-[#00D4AA]/20 border border-[#00D4AA]/30"
                  : "bg-white/[0.04] border border-white/[0.10]"
              }`}
            >
              {ach.achieved && <Check size={12} className="text-[#00D4AA]" />}
            </div>

            {/* Label */}
            <span
              className={`text-sm flex-1 ${
                ach.achieved ? "text-[#6B7280] line-through" : "text-[#B0B8C8]"
              }`}
            >
              {ach.label}
            </span>

            {/* CTA for uncompleted */}
            {!ach.achieved && ach.cta_href && (
              <Link
                href={ach.cta_href}
                className="flex items-center gap-1 text-xs font-medium text-[#6C63FF] hover:text-[#00D4AA] transition-colors whitespace-nowrap"
              >
                {ach.cta_label}
                <ArrowRight size={12} />
              </Link>
            )}
          </div>
        ))}
      </div>

      {/* Upgrade prompt for advanced users */}
      {data.achieved >= 3 && !allDone && (
        <div className="mt-4 pt-3 border-t border-white/[0.06]">
          <p className="text-xs text-[#8B95A9]">
            You&apos;re making great progress! Complete all steps to unlock the full power of your automations.
          </p>
        </div>
      )}

      {/* Achievement-based upgrade prompt */}
      {allDone && (
        <div className="mt-4 pt-3 border-t border-white/[0.06] flex items-center justify-between">
          <p className="text-xs text-[#00D4AA]">
            All setup steps complete — your automations are working for you!
          </p>
          <Link
            href="/portal/billing"
            className="text-xs font-medium text-[#6C63FF] hover:text-[#00D4AA] transition-colors whitespace-nowrap"
          >
            View plans &rarr;
          </Link>
        </div>
      )}
    </div>
  );
}
