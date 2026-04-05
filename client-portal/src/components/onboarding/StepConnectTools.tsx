"use client";

import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { TOOLS, type StepProps } from "./types";

export default function StepConnectTools({
  stepData,
  onUpdate,
  onNext,
  onSkip,
  onBack,
  loading,
}: StepProps) {
  const selected = stepData.connect_tools?.selected_tools || [];

  function toggleTool(toolId: string) {
    const next = selected.includes(toolId)
      ? selected.filter((t) => t !== toolId)
      : [...selected, toolId];
    onUpdate({ connect_tools: { selected_tools: next } });
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">
          Which tools does your business use?
        </h2>
        <p className="text-sm text-[#8B95A9]">
          Select the platforms you&apos;d like to connect. You can always add
          more later.
        </p>
      </div>

      <div className="space-y-2">
        {TOOLS.map((tool) => {
          const isSelected = selected.includes(tool.id);
          return (
            <button
              key={tool.id}
              type="button"
              onClick={() => toggleTool(tool.id)}
              className={`w-full flex items-center gap-4 px-4 py-3.5 rounded-xl transition-all duration-200 border text-left ${
                isSelected
                  ? "border-[#6C63FF] bg-[#6C63FF]/10"
                  : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.15] hover:bg-white/[0.05]"
              }`}
            >
              {/* Tool icon */}
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 text-white font-bold text-sm"
                style={{ background: `${tool.color}20`, border: `1px solid ${tool.color}40` }}
              >
                {tool.icon}
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-white block">
                  {tool.name}
                </span>
                <span className="text-xs text-[#6B7280]">
                  {tool.description}
                </span>
              </div>

              {/* Checkbox */}
              <div
                className={`w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 transition-all duration-200 ${
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

      {selected.length > 0 && (
        <p className="text-xs text-[#00D4AA]">
          {selected.length} tool{selected.length !== 1 ? "s" : ""} selected —
          we&apos;ll help you connect {selected.length === 1 ? "it" : "them"}{" "}
          after setup.
        </p>
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
