"use client";

import { useEffect } from "react";
import { ArrowLeft, ArrowRight, Zap, BarChart3, Bell, Clock } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { StepProps } from "./types";

const PREVIEW_FEATURES = [
  {
    icon: Zap,
    title: "Automated Workflows",
    description: "AI agents handle repetitive tasks 24/7 while you focus on growth.",
    color: "#6C63FF",
  },
  {
    icon: BarChart3,
    title: "Real-Time Dashboard",
    description: "Track leads, revenue, campaigns, and business health at a glance.",
    color: "#00D4AA",
  },
  {
    icon: Bell,
    title: "Smart Alerts",
    description: "Get notified about anomalies, opportunities, and actions needed.",
    color: "#FF6D5A",
  },
  {
    icon: Clock,
    title: "Time Saved",
    description: "Most businesses save 15-20 hours per week within the first month.",
    color: "#3B82F6",
  },
];

export default function StepPreview({
  stepData,
  onUpdate,
  onNext,
  onBack,
  loading,
}: StepProps) {
  const selectedTemplate = stepData.choose_automation?.selected_template;
  const primaryNeed = stepData.business_profile?.primary_need;

  // Mark as viewed (in useEffect to avoid render loop — HIGH-1 fix)
  useEffect(() => {
    if (!stepData.preview?.viewed) {
      onUpdate({ preview: { viewed: true } });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">
          Here&apos;s what&apos;s coming
        </h2>
        <p className="text-sm text-[#8B95A9]">
          {selectedTemplate
            ? "Your selected automation will be ready shortly. Here's what your portal includes."
            : "Your portal is packed with powerful features. Here's a preview."}
        </p>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {PREVIEW_FEATURES.map((feature) => (
          <div
            key={feature.title}
            className="p-4 rounded-xl border border-white/[0.08] bg-white/[0.03]"
          >
            <div
              className="w-9 h-9 rounded-lg flex items-center justify-center mb-3"
              style={{
                background: `${feature.color}15`,
                border: `1px solid ${feature.color}30`,
              }}
            >
              <feature.icon size={18} style={{ color: feature.color }} />
            </div>
            <h3 className="text-sm font-medium text-white mb-1">
              {feature.title}
            </h3>
            <p className="text-xs text-[#6B7280] leading-relaxed">
              {feature.description}
            </p>
          </div>
        ))}
      </div>

      {/* Quick preview of what the primary need enables */}
      {primaryNeed && (
        <div
          className="p-4 rounded-xl border border-[#6C63FF]/20 bg-[#6C63FF]/5"
        >
          <p className="text-sm text-white font-medium mb-1">
            {primaryNeed === "marketing"
              ? "Marketing Automation Ready"
              : primaryNeed === "accounting"
              ? "Accounting Automation Ready"
              : primaryNeed === "advisory"
              ? "Advisory Automation Ready"
              : "Full Business Automation Ready"}
          </p>
          <p className="text-xs text-[#8B95A9]">
            {primaryNeed === "marketing"
              ? "AI-generated content, multi-platform publishing, SEO monitoring, lead scoring, and ad campaign management."
              : primaryNeed === "accounting"
              ? "Automatic invoicing, payment reminders, reconciliation, supplier bill processing, and month-end reports."
              : primaryNeed === "advisory"
              ? "Client intake, meeting prep, compliance tracking, document management, and advisory workflow automation."
              : "All departments automated with cross-functional intelligence and a unified dashboard."}
          </p>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1 text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
        >
          <ArrowLeft size={14} />
          Back
        </button>
        <Button variant="coral" size="lg" onClick={onNext} loading={loading}>
          Finish Setup
          <ArrowRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  );
}
