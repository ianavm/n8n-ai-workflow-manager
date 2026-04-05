"use client";

import { ArrowRight, ChevronDown } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  INDUSTRIES,
  COMPANY_SIZES,
  PRIMARY_NEEDS,
  type StepProps,
} from "./types";

export default function StepBusinessProfile({
  stepData,
  onUpdate,
  onNext,
  onSkip,
  loading,
}: StepProps) {
  const profile = stepData.business_profile || {
    industry: "",
    company_size: "",
    primary_need: "",
    phone_number: "",
  };

  function updateField(field: string, value: string) {
    onUpdate({
      business_profile: { ...profile, [field]: value },
    });
  }

  const isComplete =
    profile.industry && profile.company_size && profile.primary_need;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-white mb-1">
          Tell us about your business
        </h2>
        <p className="text-sm text-[#8B95A9]">
          This helps us personalise your automation experience.
        </p>
      </div>

      {/* Industry */}
      <div>
        <label className="block text-xs font-medium text-[#8B95A9] mb-2 uppercase tracking-wider">
          Industry
        </label>
        <div className="relative">
          <select
            value={profile.industry}
            onChange={(e) => updateField("industry", e.target.value)}
            className="w-full appearance-none px-4 py-3 rounded-xl text-sm text-white bg-white/[0.04] border border-white/[0.08] focus:border-[#6C63FF]/50 focus:outline-none transition-colors cursor-pointer"
          >
            <option value="" disabled className="bg-[#131B36] text-[#6B7280]">
              Select your industry
            </option>
            {INDUSTRIES.map((ind) => (
              <option
                key={ind.value}
                value={ind.value}
                className="bg-[#131B36] text-white"
              >
                {ind.label}
              </option>
            ))}
          </select>
          <ChevronDown
            size={16}
            className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] pointer-events-none"
          />
        </div>
      </div>

      {/* Company Size */}
      <div>
        <label className="block text-xs font-medium text-[#8B95A9] mb-2 uppercase tracking-wider">
          Company Size
        </label>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {COMPANY_SIZES.map((size) => (
            <button
              key={size.value}
              type="button"
              onClick={() => updateField("company_size", size.value)}
              className={`px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-200 border ${
                profile.company_size === size.value
                  ? "border-[#6C63FF] bg-[#6C63FF]/10 text-white"
                  : "border-white/[0.08] bg-white/[0.03] text-[#8B95A9] hover:border-white/[0.15] hover:bg-white/[0.05]"
              }`}
            >
              {size.label}
            </button>
          ))}
        </div>
      </div>

      {/* Primary Need */}
      <div>
        <label className="block text-xs font-medium text-[#8B95A9] mb-2 uppercase tracking-wider">
          What do you need most?
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
          {PRIMARY_NEEDS.map((need) => (
            <button
              key={need.value}
              type="button"
              onClick={() => updateField("primary_need", need.value)}
              className={`text-left px-4 py-3 rounded-xl transition-all duration-200 border ${
                profile.primary_need === need.value
                  ? "border-[#6C63FF] bg-[#6C63FF]/10"
                  : "border-white/[0.08] bg-white/[0.03] hover:border-white/[0.15] hover:bg-white/[0.05]"
              }`}
            >
              <span
                className={`text-sm font-medium block ${
                  profile.primary_need === need.value
                    ? "text-white"
                    : "text-[#B0B8C8]"
                }`}
              >
                {need.label}
              </span>
              <span className="text-xs text-[#6B7280] block mt-0.5">
                {need.description}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Company Name (shown if not already set — e.g. Google SSO users) */}
      <div>
        <label className="block text-xs font-medium text-[#8B95A9] mb-1 uppercase tracking-wider">
          Company Name
        </label>
        <input
          type="text"
          value={profile.company_name || ""}
          onChange={(e) => updateField("company_name", e.target.value)}
          placeholder="Acme Corp"
          autoComplete="organization"
          className="w-full px-4 py-3 rounded-xl text-sm text-white bg-white/[0.04] border border-white/[0.08] focus:border-[#6C63FF]/50 focus:outline-none transition-colors placeholder:text-[#4B5563]"
        />
      </div>

      {/* Phone (optional) */}
      <div>
        <label className="block text-xs font-medium text-[#8B95A9] mb-1 uppercase tracking-wider">
          Phone{" "}
          <span className="text-[#4B5563] normal-case tracking-normal">
            (optional)
          </span>
        </label>
        <input
          type="tel"
          value={profile.phone_number || ""}
          onChange={(e) => updateField("phone_number", e.target.value)}
          placeholder="+27 82 123 4567"
          autoComplete="tel"
          className="w-full px-4 py-3 rounded-xl text-sm text-white bg-white/[0.04] border border-white/[0.08] focus:border-[#6C63FF]/50 focus:outline-none transition-colors placeholder:text-[#4B5563]"
        />
      </div>

      {/* Actions */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onSkip}
          className="text-sm text-[#6B7280] hover:text-[#B0B8C8] transition-colors"
        >
          Skip for now
        </button>
        <Button
          variant="coral"
          size="lg"
          onClick={onNext}
          loading={loading}
          disabled={!isComplete}
        >
          Continue
          <ArrowRight size={16} className="ml-1" />
        </Button>
      </div>
    </div>
  );
}
