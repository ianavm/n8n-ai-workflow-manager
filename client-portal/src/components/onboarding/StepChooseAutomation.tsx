"use client";

import { useState, useEffect } from "react";
import { ArrowLeft, ArrowRight, Clock, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import type { StepProps, AutomationTemplate } from "./types";

export default function StepChooseAutomation({
  stepData,
  onUpdate,
  onNext,
  onSkip,
  onBack,
  loading,
}: StepProps) {
  const [templates, setTemplates] = useState<AutomationTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(true);

  const selectedId = stepData.choose_automation?.selected_template || null;
  const industry = stepData.business_profile?.industry || "";
  const primaryNeed = stepData.business_profile?.primary_need || "";

  useEffect(() => {
    async function fetchTemplates() {
      try {
        const params = new URLSearchParams();
        if (industry) params.set("industry", industry);
        if (primaryNeed) params.set("primary_need", primaryNeed);

        const res = await fetch(
          `/api/portal/onboarding/templates?${params.toString()}`
        );
        if (res.ok) {
          const data = await res.json();
          setTemplates(data.templates || []);
        }
      } catch {
        // Silently fall back to empty templates
      }
      setLoadingTemplates(false);
    }
    fetchTemplates();
  }, [industry, primaryNeed]);

  function selectTemplate(templateId: string) {
    const next =
      selectedId === templateId ? null : templateId;
    onUpdate({ choose_automation: { selected_template: next } });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">
          Choose your first automation
        </h2>
        <p className="text-sm text-[#8B95A9]">
          Pick a workflow to start with — you can always add more from your
          dashboard.
        </p>
      </div>

      {loadingTemplates ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div
              key={i}
              className="h-20 rounded-xl animate-pulse"
              style={{ background: "rgba(255,255,255,0.04)" }}
            />
          ))}
        </div>
      ) : templates.length === 0 ? (
        <div className="text-center py-8">
          <p className="text-sm text-[#6B7280]">
            No templates available yet. Skip this step and explore automations
            from your dashboard.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {templates.map((tmpl) => {
            const isSelected = selectedId === tmpl.id;
            return (
              <button
                key={tmpl.id}
                type="button"
                onClick={() => selectTemplate(tmpl.id)}
                className={`w-full flex items-start gap-4 px-4 py-3.5 rounded-xl transition-all duration-200 border text-left ${
                  isSelected
                    ? "border-[#6C63FF] bg-[#6C63FF]/10"
                    : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.15] hover:bg-white/[0.05]"
                }`}
              >
                {/* Icon */}
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 text-lg"
                  style={{
                    background: "rgba(108, 99, 255, 0.1)",
                    border: "1px solid rgba(108, 99, 255, 0.2)",
                  }}
                >
                  {tmpl.icon}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-white block">
                    {tmpl.name}
                  </span>
                  <span className="text-xs text-[#6B7280] block mt-0.5">
                    {tmpl.description}
                  </span>
                  <div className="flex items-center gap-1 mt-1.5 text-[#00D4AA]">
                    <Clock size={12} />
                    <span className="text-xs">
                      Saves ~{tmpl.time_saved}
                    </span>
                  </div>
                </div>

                {/* Selection indicator */}
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5 transition-all duration-200 ${
                    isSelected
                      ? "bg-[#6C63FF]"
                      : "bg-white/[0.04] border border-white/[0.12]"
                  }`}
                >
                  {isSelected && <Check size={14} className="text-white" />}
                </div>
              </button>
            );
          })}
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={onBack}
            className="flex items-center gap-1 text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
          >
            <ArrowLeft size={14} />
            Back
          </button>
          <button
            type="button"
            onClick={onSkip}
            className="text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
          >
            Skip for now
          </button>
        </div>
        <Button variant="coral" size="lg" onClick={onNext} loading={loading}>
          Continue
          <ArrowRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  );
}
