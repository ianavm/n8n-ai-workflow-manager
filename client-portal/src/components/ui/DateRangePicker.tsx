"use client";

import { useState } from "react";

export type DateRange = "7d" | "30d" | "90d" | "custom";

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange, startDate?: string, endDate?: string) => void;
  customStart?: string;
  customEnd?: string;
}

export function DateRangePicker({
  value,
  onChange,
  customStart,
  customEnd,
}: DateRangePickerProps) {
  const [showCustom, setShowCustom] = useState(value === "custom");

  const presets: { label: string; value: DateRange }[] = [
    { label: "7 Days", value: "7d" },
    { label: "30 Days", value: "30d" },
    { label: "90 Days", value: "90d" },
    { label: "Custom", value: "custom" },
  ];

  return (
    <div className="flex flex-wrap items-center gap-2">
      {presets.map((preset) => (
        <button
          key={preset.value}
          onClick={() => {
            if (preset.value === "custom") {
              setShowCustom(true);
            } else {
              setShowCustom(false);
            }
            onChange(preset.value);
          }}
          className={`px-3 py-1.5 text-xs font-medium rounded-lg transition-all ${
            value === preset.value
              ? "bg-[rgba(108,99,255,0.15)] text-[#6C63FF] border border-[rgba(108,99,255,0.3)]"
              : "bg-[rgba(255,255,255,0.05)] text-[#6B7280] border border-transparent hover:text-[#B0B8C8] hover:bg-[rgba(255,255,255,0.08)]"
          }`}
        >
          {preset.label}
        </button>
      ))}

      {showCustom && (
        <div className="flex items-center gap-2 ml-2">
          <input
            type="date"
            value={customStart || ""}
            onChange={(e) => onChange("custom", e.target.value, customEnd)}
            className="px-2 py-1 text-xs rounded-lg bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8]"
          />
          <span className="text-[#6B7280] text-xs">to</span>
          <input
            type="date"
            value={customEnd || ""}
            onChange={(e) => onChange("custom", customStart, e.target.value)}
            className="px-2 py-1 text-xs rounded-lg bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-[#B0B8C8]"
          />
        </div>
      )}
    </div>
  );
}
