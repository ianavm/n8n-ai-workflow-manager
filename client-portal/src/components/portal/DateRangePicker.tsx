"use client";

import { useState } from "react";
import { format, startOfToday, subDays } from "date-fns";
import { Calendar as CalendarIcon } from "lucide-react";

import { cn } from "@/lib/utils";
import { Button } from "@/components/ui-shadcn/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui-shadcn/popover";

export interface DateRange {
  from: Date;
  to: Date;
}

interface DateRangePickerProps {
  value: DateRange;
  onChange: (range: DateRange) => void;
  className?: string;
}

const PRESETS: Array<{ label: string; range: () => DateRange }> = [
  { label: "Last 7 days",  range: () => ({ from: subDays(startOfToday(), 6),  to: startOfToday() }) },
  { label: "Last 14 days", range: () => ({ from: subDays(startOfToday(), 13), to: startOfToday() }) },
  { label: "Last 30 days", range: () => ({ from: subDays(startOfToday(), 29), to: startOfToday() }) },
  { label: "Last 60 days", range: () => ({ from: subDays(startOfToday(), 59), to: startOfToday() }) },
  { label: "Last 90 days", range: () => ({ from: subDays(startOfToday(), 89), to: startOfToday() }) },
];

/**
 * Lightweight date range selector — preset-driven (no calendar widget this
 * phase). Matches the website's pill aesthetic and covers the 95% case.
 * Full calendar can be layered in later if needed.
 */
export function DateRangePicker({ value, onChange, className }: DateRangePickerProps) {
  const [open, setOpen] = useState(false);

  const label =
    value.from && value.to
      ? `${format(value.from, "MMM d")} – ${format(value.to, "MMM d, yyyy")}`
      : "Select range";

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={cn("gap-2 font-medium", className)}
          aria-label="Select date range"
        >
          <CalendarIcon className="size-3.5" />
          {label}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-56 p-2">
        <ul className="flex flex-col gap-1">
          {PRESETS.map((preset) => (
            <li key={preset.label}>
              <button
                type="button"
                onClick={() => {
                  onChange(preset.range());
                  setOpen(false);
                }}
                className="w-full text-left text-sm font-medium rounded-[var(--radius-sm)] px-3 py-2 text-[var(--text-muted)] hover:text-foreground hover:bg-[var(--bg-card-hover)] transition-colors"
              >
                {preset.label}
              </button>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
