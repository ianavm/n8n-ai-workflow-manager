"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, Check } from "lucide-react";
import Link from "next/link";

// -- Types -------------------------------------------------------------------

interface FormData {
  name: string;
  campaign_type: string;
  notes: string;
  platform: string;
  budget_total: string;
  budget_daily: string;
  start_date: string;
  end_date: string;
  locations: string;
  age_min: string;
  age_max: string;
  interests: string;
}

const INITIAL_FORM: FormData = {
  name: "",
  campaign_type: "",
  notes: "",
  platform: "",
  budget_total: "",
  budget_daily: "",
  start_date: "",
  end_date: "",
  locations: "",
  age_min: "",
  age_max: "",
  interests: "",
};

const CAMPAIGN_TYPES = [
  { value: "awareness", label: "Awareness" },
  { value: "traffic", label: "Traffic" },
  { value: "engagement", label: "Engagement" },
  { value: "leads", label: "Leads" },
  { value: "conversions", label: "Conversions" },
  { value: "sales", label: "Sales" },
  { value: "app_install", label: "App Install" },
];

const PLATFORMS = [
  { value: "google_ads", label: "Google Ads" },
  { value: "meta_ads", label: "Meta Ads" },
  { value: "tiktok_ads", label: "TikTok Ads" },
  { value: "linkedin_ads", label: "LinkedIn Ads" },
  { value: "multi_platform", label: "Multi-Platform" },
];

const STEPS = ["Basic Info", "Platform & Budget", "Targeting & Dates", "Review & Submit"];

// -- Helpers -----------------------------------------------------------------

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 2 })}`;
}

function labelFor(value: string, options: { value: string; label: string }[]): string {
  return options.find((o) => o.value === value)?.label ?? value;
}

// -- Component ---------------------------------------------------------------

export default function NewCampaignPage() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormData>(INITIAL_FORM);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function update(field: keyof FormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function canAdvance(): boolean {
    if (step === 0) return form.name.trim().length > 0 && form.campaign_type !== "";
    if (step === 1) return form.platform !== "";
    return true;
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);

    const targeting: Record<string, unknown> = {};
    if (form.locations.trim()) {
      targeting.locations = form.locations.split(",").map((s) => s.trim()).filter(Boolean);
    }
    if (form.age_min || form.age_max) {
      targeting.age_range = {
        min: form.age_min ? parseInt(form.age_min, 10) : undefined,
        max: form.age_max ? parseInt(form.age_max, 10) : undefined,
      };
    }
    if (form.interests.trim()) {
      targeting.interests = form.interests.split(",").map((s) => s.trim()).filter(Boolean);
    }

    const payload = {
      name: form.name.trim(),
      campaign_type: form.campaign_type,
      platform: form.platform,
      budget_total: form.budget_total ? Math.round(parseFloat(form.budget_total) * 100) : 0,
      budget_daily: form.budget_daily ? Math.round(parseFloat(form.budget_daily) * 100) : 0,
      start_date: form.start_date || undefined,
      end_date: form.end_date || undefined,
      notes: form.notes.trim() || undefined,
      targeting: Object.keys(targeting).length > 0 ? targeting : undefined,
    };

    try {
      const res = await fetch("/api/portal/marketing/campaigns", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const json = await res.json();

      if (!res.ok) {
        setError(json.error ?? "Failed to create campaign");
        setSubmitting(false);
        return;
      }

      router.push(`/portal/marketing/campaigns/${json.data.id}`);
    } catch {
      setError("Network error. Please try again.");
      setSubmitting(false);
    }
  }

  // -- Input classes ---------------------------------------------------------

  const inputClass =
    "w-full px-3 py-2.5 rounded-lg text-sm text-white bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] focus:outline-none focus:border-[#10B981] transition-colors placeholder:text-[#6B7280]";
  const labelClass = "block text-sm text-[#B0B8C8] mb-1.5";
  const selectClass =
    "w-full px-3 py-2.5 rounded-lg text-sm text-white bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] focus:outline-none focus:border-[#10B981] transition-colors";

  // -- Step Indicator --------------------------------------------------------

  function StepIndicator() {
    return (
      <div className="flex items-center justify-between mb-8">
        {STEPS.map((label, i) => {
          const isActive = i === step;
          const isCompleted = i < step;
          return (
            <div key={label} className="flex items-center gap-2 flex-1">
              <div
                className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-[#10B981] text-white"
                    : isCompleted
                    ? "bg-[#10B981]/20 text-[#10B981]"
                    : "bg-[rgba(255,255,255,0.05)] text-[#6B7280]"
                }`}
              >
                {isCompleted ? <Check size={14} /> : i + 1}
              </div>
              <span
                className={`text-xs hidden sm:inline ${
                  isActive ? "text-white font-medium" : "text-[#6B7280]"
                }`}
              >
                {label}
              </span>
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-px mx-2 ${
                    isCompleted
                      ? "bg-[#10B981]/40"
                      : "bg-[rgba(255,255,255,0.06)]"
                  }`}
                />
              )}
            </div>
          );
        })}
      </div>
    );
  }

  // -- Step Panels -----------------------------------------------------------

  function StepBasicInfo() {
    return (
      <div className="floating-card p-6 space-y-5">
        <h2 className="text-lg font-semibold text-white">Basic Information</h2>

        <div>
          <label className={labelClass}>Campaign Name *</label>
          <input
            type="text"
            className={inputClass}
            placeholder="e.g. Summer Lead Gen 2026"
            value={form.name}
            onChange={(e) => update("name", e.target.value)}
            maxLength={200}
          />
        </div>

        <div>
          <label className={labelClass}>Campaign Type *</label>
          <select
            className={selectClass}
            value={form.campaign_type}
            onChange={(e) => update("campaign_type", e.target.value)}
          >
            <option value="">Select type...</option>
            {CAMPAIGN_TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className={labelClass}>Notes</label>
          <textarea
            className={`${inputClass} min-h-[80px] resize-y`}
            placeholder="Optional campaign notes..."
            value={form.notes}
            onChange={(e) => update("notes", e.target.value)}
            rows={3}
          />
        </div>
      </div>
    );
  }

  function StepPlatformBudget() {
    return (
      <div className="floating-card p-6 space-y-5">
        <h2 className="text-lg font-semibold text-white">Platform & Budget</h2>

        <div>
          <label className={labelClass}>Platform *</label>
          <select
            className={selectClass}
            value={form.platform}
            onChange={(e) => update("platform", e.target.value)}
          >
            <option value="">Select platform...</option>
            {PLATFORMS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Total Budget (ZAR)</label>
            <input
              type="number"
              className={inputClass}
              placeholder="e.g. 25000"
              value={form.budget_total}
              onChange={(e) => update("budget_total", e.target.value)}
              min={0}
              step={0.01}
            />
          </div>
          <div>
            <label className={labelClass}>Daily Budget (ZAR)</label>
            <input
              type="number"
              className={inputClass}
              placeholder="e.g. 500"
              value={form.budget_daily}
              onChange={(e) => update("budget_daily", e.target.value)}
              min={0}
              step={0.01}
            />
          </div>
        </div>
      </div>
    );
  }

  function StepTargetingDates() {
    return (
      <div className="floating-card p-6 space-y-5">
        <h2 className="text-lg font-semibold text-white">Targeting & Dates</h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Start Date</label>
            <input
              type="date"
              className={inputClass}
              value={form.start_date}
              onChange={(e) => update("start_date", e.target.value)}
            />
          </div>
          <div>
            <label className={labelClass}>End Date</label>
            <input
              type="date"
              className={inputClass}
              value={form.end_date}
              onChange={(e) => update("end_date", e.target.value)}
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Locations (comma-separated)</label>
          <input
            type="text"
            className={inputClass}
            placeholder="e.g. Johannesburg, Cape Town, Pretoria"
            value={form.locations}
            onChange={(e) => update("locations", e.target.value)}
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelClass}>Age Min</label>
            <input
              type="number"
              className={inputClass}
              placeholder="e.g. 25"
              value={form.age_min}
              onChange={(e) => update("age_min", e.target.value)}
              min={13}
              max={65}
            />
          </div>
          <div>
            <label className={labelClass}>Age Max</label>
            <input
              type="number"
              className={inputClass}
              placeholder="e.g. 55"
              value={form.age_max}
              onChange={(e) => update("age_max", e.target.value)}
              min={13}
              max={65}
            />
          </div>
        </div>

        <div>
          <label className={labelClass}>Interests (comma-separated)</label>
          <input
            type="text"
            className={inputClass}
            placeholder="e.g. Digital Marketing, Small Business, E-commerce"
            value={form.interests}
            onChange={(e) => update("interests", e.target.value)}
          />
        </div>
      </div>
    );
  }

  function StepReview() {
    const budgetTotalCents = form.budget_total
      ? Math.round(parseFloat(form.budget_total) * 100)
      : 0;
    const budgetDailyCents = form.budget_daily
      ? Math.round(parseFloat(form.budget_daily) * 100)
      : 0;

    return (
      <div className="floating-card p-6 space-y-5">
        <h2 className="text-lg font-semibold text-white">Review Campaign</h2>

        <div className="space-y-4">
          {/* Basic */}
          <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.03)]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-[#B0B8C8]">Basic Info</h3>
              <button
                type="button"
                onClick={() => setStep(0)}
                className="text-xs text-[#10B981] hover:underline"
              >
                Edit
              </button>
            </div>
            <div className="space-y-1 text-sm">
              <p className="text-white">{form.name}</p>
              <p className="text-[#6B7280]">
                Type: {labelFor(form.campaign_type, CAMPAIGN_TYPES)}
              </p>
              {form.notes && (
                <p className="text-[#6B7280]">Notes: {form.notes}</p>
              )}
            </div>
          </div>

          {/* Platform & Budget */}
          <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.03)]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-[#B0B8C8]">
                Platform & Budget
              </h3>
              <button
                type="button"
                onClick={() => setStep(1)}
                className="text-xs text-[#10B981] hover:underline"
              >
                Edit
              </button>
            </div>
            <div className="space-y-1 text-sm">
              <p className="text-white">{labelFor(form.platform, PLATFORMS)}</p>
              <p className="text-[#6B7280]">
                Total: {budgetTotalCents > 0 ? formatZAR(budgetTotalCents) : "Not set"}
                {budgetDailyCents > 0 && ` | Daily: ${formatZAR(budgetDailyCents)}`}
              </p>
            </div>
          </div>

          {/* Targeting & Dates */}
          <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.03)]">
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-medium text-[#B0B8C8]">
                Targeting & Dates
              </h3>
              <button
                type="button"
                onClick={() => setStep(2)}
                className="text-xs text-[#10B981] hover:underline"
              >
                Edit
              </button>
            </div>
            <div className="space-y-1 text-sm">
              <p className="text-[#6B7280]">
                Start:{" "}
                {form.start_date
                  ? new Date(form.start_date).toLocaleDateString("en-ZA")
                  : "Not set"}
                {form.end_date && (
                  <>
                    {" "}
                    &rarr;{" "}
                    {new Date(form.end_date).toLocaleDateString("en-ZA")}
                  </>
                )}
              </p>
              {form.locations && (
                <p className="text-[#6B7280]">Locations: {form.locations}</p>
              )}
              {(form.age_min || form.age_max) && (
                <p className="text-[#6B7280]">
                  Age: {form.age_min || "?"} - {form.age_max || "?"}
                </p>
              )}
              {form.interests && (
                <p className="text-[#6B7280]">Interests: {form.interests}</p>
              )}
            </div>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-red-400">
            {error}
          </div>
        )}
      </div>
    );
  }

  // -- Render ----------------------------------------------------------------

  const stepPanels = [
    <StepBasicInfo key="basic" />,
    <StepPlatformBudget key="budget" />,
    <StepTargetingDates key="targeting" />,
    <StepReview key="review" />,
  ];

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Link
          href="/portal/marketing/campaigns"
          className="p-2 rounded-lg hover:bg-[rgba(255,255,255,0.05)] transition-colors"
        >
          <ArrowLeft size={18} className="text-[#B0B8C8]" />
        </Link>
        <h1 className="text-2xl font-bold text-white">New Campaign</h1>
      </div>

      {/* Step Indicator */}
      <StepIndicator />

      {/* Current Step Panel */}
      {stepPanels[step]}

      {/* Navigation */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={() => setStep((s) => s - 1)}
          disabled={step === 0}
          className={`px-4 py-2.5 rounded-lg text-sm font-medium transition-colors ${
            step === 0
              ? "opacity-0 pointer-events-none"
              : "text-[#B0B8C8] bg-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.08)]"
          }`}
        >
          Back
        </button>

        {step < STEPS.length - 1 ? (
          <button
            type="button"
            onClick={() => setStep((s) => s + 1)}
            disabled={!canAdvance()}
            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            style={{
              background: canAdvance()
                ? "linear-gradient(135deg, #10B981, #059669)"
                : undefined,
              backgroundColor: canAdvance() ? undefined : "rgba(255,255,255,0.05)",
            }}
          >
            Next
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-60"
            style={{
              background: "linear-gradient(135deg, #10B981, #059669)",
            }}
          >
            {submitting ? "Creating..." : "Create Campaign"}
          </button>
        )}
      </div>
    </div>
  );
}
