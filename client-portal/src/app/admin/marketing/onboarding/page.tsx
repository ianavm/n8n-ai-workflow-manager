"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ChevronLeft,
  ChevronRight,
  Check,
  Loader2,
  UserPlus,
} from "lucide-react";

/* ────────────────────────────────────────────
   Types
   ──────────────────────────────────────────── */

interface ClientOption {
  id: string;
  full_name: string;
  email: string;
}

interface WizardState {
  client_id: string;
  platforms_enabled: string[];
  ad_platform_config: Record<string, Record<string, string>>;
  n8n_credentials: Record<string, string>;
  budget_monthly_cap: number; // rands (converted to cents on submit)
  budget_alert_threshold: number; // 0-100
  ai_model: string;
  auto_approve: boolean;
  lead_assignment_mode: string;
}

const INITIAL_STATE: WizardState = {
  client_id: "",
  platforms_enabled: [],
  ad_platform_config: {},
  n8n_credentials: {},
  budget_monthly_cap: 0,
  budget_alert_threshold: 80,
  ai_model: "anthropic/claude-sonnet-4-20250514",
  auto_approve: false,
  lead_assignment_mode: "round_robin",
};

const PLATFORMS = [
  { value: "google_ads", label: "Google Ads" },
  { value: "meta_ads", label: "Meta Ads" },
  { value: "tiktok_ads", label: "TikTok Ads" },
  { value: "linkedin_ads", label: "LinkedIn Ads" },
  { value: "blotato", label: "Blotato (Content Posting)" },
] as const;

const PLATFORM_FIELDS: Record<string, { key: string; label: string; placeholder: string }[]> = {
  google_ads: [
    { key: "customer_id", label: "Customer ID", placeholder: "123-456-7890" },
    { key: "manager_id", label: "Manager ID", placeholder: "123-456-7890" },
  ],
  meta_ads: [
    { key: "account_id", label: "Account ID", placeholder: "act_123456789" },
    { key: "pixel_id", label: "Pixel ID", placeholder: "123456789" },
  ],
  tiktok_ads: [
    { key: "advertiser_id", label: "Advertiser ID", placeholder: "123456789" },
  ],
  linkedin_ads: [
    { key: "account_id", label: "Account ID", placeholder: "123456789" },
  ],
};

const AI_MODELS = [
  { value: "anthropic/claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "openai/gpt-4o", label: "GPT-4o" },
] as const;

const STEPS = [
  "Select Client",
  "Enable Platforms",
  "Platform Config",
  "n8n Credentials",
  "Budget & Content",
  "Review & Create",
] as const;

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

/* ────────────────────────────────────────────
   Component
   ──────────────────────────────────────────── */

export default function OnboardingWizard() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>({ ...INITIAL_STATE });
  const [clients, setClients] = useState<ClientOption[]>([]);
  const [loadingClients, setLoadingClients] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  /* Load clients without existing mkt_config */
  const loadClients = useCallback(async () => {
    try {
      const [allRes, configRes] = await Promise.all([
        fetch("/api/admin/marketing/config?clients_without_config=true"),
        fetch("/api/admin/marketing/config"),
      ]);

      if (!allRes.ok || !configRes.ok) {
        throw new Error("Failed to load clients");
      }

      const allJson = await allRes.json();
      setClients(allJson.data ?? []);
    } catch {
      setClients([]);
    } finally {
      setLoadingClients(false);
    }
  }, []);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  /* Immutable state updaters */
  const updateState = useCallback(
    <K extends keyof WizardState>(key: K, value: WizardState[K]) => {
      setState((prev) => ({ ...prev, [key]: value }));
    },
    []
  );

  const togglePlatform = useCallback((platform: string) => {
    setState((prev) => {
      const enabled = prev.platforms_enabled.includes(platform)
        ? prev.platforms_enabled.filter((p) => p !== platform)
        : [...prev.platforms_enabled, platform];
      return { ...prev, platforms_enabled: enabled };
    });
  }, []);

  const updatePlatformConfig = useCallback(
    (platform: string, key: string, value: string) => {
      setState((prev) => ({
        ...prev,
        ad_platform_config: {
          ...prev.ad_platform_config,
          [platform]: {
            ...(prev.ad_platform_config[platform] ?? {}),
            [key]: value,
          },
        },
      }));
    },
    []
  );

  const updateCredential = useCallback((platform: string, value: string) => {
    setState((prev) => ({
      ...prev,
      n8n_credentials: { ...prev.n8n_credentials, [platform]: value },
    }));
  }, []);

  /* Validation per step */
  const canProceed = (): boolean => {
    switch (step) {
      case 0:
        return state.client_id.length > 0;
      case 1:
        return state.platforms_enabled.length > 0;
      case 2:
        return true; // Platform config is optional
      case 3:
        return true; // Credentials are optional at onboard time
      case 4:
        return state.budget_monthly_cap >= 0;
      case 5:
        return true;
      default:
        return false;
    }
  };

  /* Submit */
  const handleSubmit = async () => {
    setSubmitting(true);
    setSubmitError(null);

    const adPlatformConfig: Record<string, Record<string, string>> = {};
    for (const p of state.platforms_enabled) {
      if (state.ad_platform_config[p]) {
        adPlatformConfig[p] = { ...state.ad_platform_config[p] };
      }
    }

    const n8nCreds: Record<string, string> = {};
    for (const p of state.platforms_enabled) {
      if (state.n8n_credentials[p]) {
        n8nCreds[p] = state.n8n_credentials[p];
      }
    }

    const payload = {
      client_id: state.client_id,
      platforms_enabled: state.platforms_enabled,
      ad_platform_config: adPlatformConfig,
      n8n_credentials: n8nCreds,
      budget_monthly_cap: Math.round(state.budget_monthly_cap * 100), // rands -> cents
      budget_alert_threshold: state.budget_alert_threshold / 100, // pct -> decimal
      content_config: {
        auto_approve: state.auto_approve,
        ai_model: state.ai_model,
        posting_times: { weekday: "10:00", weekend: "12:00" },
      },
      lead_assignment_mode: state.lead_assignment_mode,
    };

    try {
      const res = await fetch("/api/admin/marketing/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({ error: "Request failed" }));
        throw new Error(body.error ?? body.details ?? `HTTP ${res.status}`);
      }

      router.push("/admin/marketing");
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : "Failed to create config");
    } finally {
      setSubmitting(false);
    }
  };

  const selectedClient = clients.find((c) => c.id === state.client_id);

  /* ──────────────── Render Steps ──────────────── */

  const renderStep = () => {
    switch (step) {
      /* Step 0: Select Client */
      case 0:
        return (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">Select Client</h2>
            <p className="text-sm text-[#6B7280]">
              Choose a client that does not yet have marketing configured.
            </p>
            {loadingClients ? (
              <div className="flex items-center gap-2 text-[#6B7280] py-8">
                <Loader2 size={16} className="animate-spin" /> Loading clients...
              </div>
            ) : clients.length === 0 ? (
              <div className="floating-card p-6 text-center">
                <p className="text-[#6B7280]">All clients already have marketing configured.</p>
              </div>
            ) : (
              <div className="space-y-2">
                {clients.map((client) => (
                  <button
                    key={client.id}
                    onClick={() => updateState("client_id", client.id)}
                    className={`w-full flex items-center justify-between p-4 rounded-lg text-left transition-all ${
                      state.client_id === client.id
                        ? "bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.3)]"
                        : "bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.04)]"
                    }`}
                  >
                    <div>
                      <p className="text-sm font-medium text-white">{client.full_name}</p>
                      <p className="text-xs text-[#6B7280]">{client.email}</p>
                    </div>
                    {state.client_id === client.id && (
                      <Check size={18} className="text-[#10B981]" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        );

      /* Step 1: Enable Platforms */
      case 1:
        return (
          <div className="space-y-4">
            <h2 className="text-lg font-semibold text-white">Enable Platforms</h2>
            <p className="text-sm text-[#6B7280]">
              Select which advertising and content platforms to activate.
            </p>
            <div className="space-y-2">
              {PLATFORMS.map(({ value, label }) => (
                <button
                  key={value}
                  onClick={() => togglePlatform(value)}
                  className={`w-full flex items-center justify-between p-4 rounded-lg text-left transition-all ${
                    state.platforms_enabled.includes(value)
                      ? "bg-[rgba(16,185,129,0.1)] border border-[rgba(16,185,129,0.3)]"
                      : "bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)] hover:bg-[rgba(255,255,255,0.04)]"
                  }`}
                >
                  <span className="text-sm font-medium text-white">{label}</span>
                  <div
                    className={`w-5 h-5 rounded flex items-center justify-center transition-all ${
                      state.platforms_enabled.includes(value)
                        ? "bg-[#10B981]"
                        : "border border-[rgba(255,255,255,0.2)]"
                    }`}
                  >
                    {state.platforms_enabled.includes(value) && (
                      <Check size={14} className="text-white" />
                    )}
                  </div>
                </button>
              ))}
            </div>
          </div>
        );

      /* Step 2: Platform Config */
      case 2: {
        const adPlatforms = state.platforms_enabled.filter(
          (p) => PLATFORM_FIELDS[p]
        );
        return (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-white">Platform Configuration</h2>
            <p className="text-sm text-[#6B7280]">
              Enter platform-specific account identifiers. Leave blank to configure later.
            </p>
            {adPlatforms.length === 0 ? (
              <p className="text-sm text-[#6B7280]">
                No ad platforms selected that require configuration. You can proceed.
              </p>
            ) : (
              adPlatforms.map((platform) => (
                <div key={platform} className="space-y-3">
                  <h3 className="text-sm font-medium text-[#10B981]">
                    {PLATFORMS.find((p) => p.value === platform)?.label}
                  </h3>
                  {PLATFORM_FIELDS[platform].map((field) => (
                    <div key={field.key}>
                      <label className="block text-xs text-[#6B7280] mb-1">
                        {field.label}
                      </label>
                      <input
                        type="text"
                        value={
                          state.ad_platform_config[platform]?.[field.key] ?? ""
                        }
                        onChange={(e) =>
                          updatePlatformConfig(platform, field.key, e.target.value)
                        }
                        placeholder={field.placeholder}
                        className="w-full px-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm placeholder-[#4B5563] focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
                      />
                    </div>
                  ))}
                </div>
              ))
            )}
          </div>
        );
      }

      /* Step 3: n8n Credential IDs */
      case 3: {
        const adPlatforms = state.platforms_enabled.filter(
          (p) => PLATFORM_FIELDS[p]
        );
        return (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-white">n8n Credential IDs</h2>
            <p className="text-sm text-[#6B7280]">
              Enter the n8n credential ID for each platform. These are used by workflows at runtime.
            </p>
            {adPlatforms.length === 0 ? (
              <p className="text-sm text-[#6B7280]">
                No ad platforms require n8n credentials. You can proceed.
              </p>
            ) : (
              adPlatforms.map((platform) => (
                <div key={platform}>
                  <label className="block text-xs text-[#6B7280] mb-1">
                    {PLATFORMS.find((p) => p.value === platform)?.label} Credential ID
                  </label>
                  <input
                    type="text"
                    value={state.n8n_credentials[platform] ?? ""}
                    onChange={(e) => updateCredential(platform, e.target.value)}
                    placeholder="e.g. AbCdEfGh1234"
                    className="w-full px-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm placeholder-[#4B5563] focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
                  />
                </div>
              ))
            )}
          </div>
        );
      }

      /* Step 4: Budget & Content Config */
      case 4:
        return (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-white">Budget & Content</h2>

            <div>
              <label className="block text-xs text-[#6B7280] mb-1">
                Monthly Budget Cap (ZAR)
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280] text-sm">
                  R
                </span>
                <input
                  type="number"
                  min={0}
                  step={100}
                  value={state.budget_monthly_cap || ""}
                  onChange={(e) =>
                    updateState(
                      "budget_monthly_cap",
                      Math.max(0, parseFloat(e.target.value) || 0)
                    )
                  }
                  placeholder="0"
                  className="w-full pl-8 pr-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm placeholder-[#4B5563] focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
                />
              </div>
              <p className="text-xs text-[#4B5563] mt-1">Set to 0 for no cap</p>
            </div>

            <div>
              <label className="block text-xs text-[#6B7280] mb-1">
                Alert Threshold ({state.budget_alert_threshold}%)
              </label>
              <input
                type="range"
                min={0}
                max={100}
                value={state.budget_alert_threshold}
                onChange={(e) =>
                  updateState("budget_alert_threshold", parseInt(e.target.value, 10))
                }
                className="w-full accent-[#10B981]"
              />
              <div className="flex justify-between text-xs text-[#4B5563]">
                <span>0%</span>
                <span>50%</span>
                <span>100%</span>
              </div>
            </div>

            <div>
              <label className="block text-xs text-[#6B7280] mb-1">AI Model</label>
              <select
                value={state.ai_model}
                onChange={(e) => updateState("ai_model", e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
              >
                {AI_MODELS.map(({ value, label }) => (
                  <option key={value} value={value} className="bg-[#1A1A2E]">
                    {label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-white">Auto-approve content</p>
                <p className="text-xs text-[#4B5563]">
                  AI-generated content will be posted without manual review
                </p>
              </div>
              <button
                onClick={() => updateState("auto_approve", !state.auto_approve)}
                className={`relative w-11 h-6 rounded-full transition-colors ${
                  state.auto_approve
                    ? "bg-[#10B981]"
                    : "bg-[rgba(255,255,255,0.1)]"
                }`}
              >
                <span
                  className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                    state.auto_approve ? "translate-x-5" : "translate-x-0"
                  }`}
                />
              </button>
            </div>

            <div>
              <label className="block text-xs text-[#6B7280] mb-1">
                Lead Assignment Mode
              </label>
              <select
                value={state.lead_assignment_mode}
                onChange={(e) =>
                  updateState("lead_assignment_mode", e.target.value)
                }
                className="w-full px-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
              >
                <option value="round_robin" className="bg-[#1A1A2E]">
                  Round Robin
                </option>
                <option value="manual" className="bg-[#1A1A2E]">
                  Manual
                </option>
                <option value="auto_score" className="bg-[#1A1A2E]">
                  Auto Score
                </option>
              </select>
            </div>
          </div>
        );

      /* Step 5: Review & Create */
      case 5:
        return (
          <div className="space-y-6">
            <h2 className="text-lg font-semibold text-white">Review & Create</h2>
            <p className="text-sm text-[#6B7280]">
              Verify all settings before creating the marketing configuration.
            </p>

            <div className="space-y-4">
              {/* Client */}
              <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)]">
                <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-1">Client</p>
                <p className="text-sm text-white font-medium">
                  {selectedClient?.full_name ?? "Unknown"}
                </p>
                <p className="text-xs text-[#6B7280]">{selectedClient?.email}</p>
              </div>

              {/* Platforms */}
              <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)]">
                <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-2">
                  Platforms
                </p>
                <div className="flex flex-wrap gap-2">
                  {state.platforms_enabled.map((p) => (
                    <span
                      key={p}
                      className="px-3 py-1 rounded-full text-xs font-medium bg-[rgba(16,185,129,0.1)] text-[#10B981]"
                    >
                      {PLATFORMS.find((pl) => pl.value === p)?.label ?? p}
                    </span>
                  ))}
                </div>
              </div>

              {/* Budget */}
              <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)]">
                <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-1">
                  Budget
                </p>
                <p className="text-sm text-white">
                  {state.budget_monthly_cap > 0
                    ? `${formatZAR(Math.round(state.budget_monthly_cap * 100))} /month`
                    : "No cap"}
                  {" | "}Alert at {state.budget_alert_threshold}%
                </p>
              </div>

              {/* Content */}
              <div className="p-4 rounded-lg bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)]">
                <p className="text-xs text-[#6B7280] uppercase tracking-wider mb-1">
                  Content & Leads
                </p>
                <p className="text-sm text-white">
                  AI: {AI_MODELS.find((m) => m.value === state.ai_model)?.label ?? state.ai_model}
                  {" | "}
                  Auto-approve: {state.auto_approve ? "Yes" : "No"}
                  {" | "}
                  Lead assign: {state.lead_assignment_mode.replace(/_/g, " ")}
                </p>
              </div>
            </div>

            {submitError && (
              <div className="p-3 rounded-lg bg-[rgba(239,68,68,0.1)] border border-[rgba(239,68,68,0.3)] text-sm text-red-400">
                {submitError}
              </div>
            )}
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-[rgba(16,185,129,0.1)] flex items-center justify-center">
          <UserPlus size={20} className="text-[#10B981]" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-white">Client Onboarding</h1>
          <p className="text-sm text-[#B0B8C8]">
            Configure marketing for a new client
          </p>
        </div>
      </div>

      {/* Step Indicator */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2">
        {STEPS.map((label, i) => (
          <button
            key={label}
            onClick={() => i < step && setStep(i)}
            disabled={i > step}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium whitespace-nowrap transition-all ${
              i === step
                ? "bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.3)]"
                : i < step
                  ? "bg-[rgba(16,185,129,0.08)] text-[#10B981] cursor-pointer hover:bg-[rgba(16,185,129,0.12)]"
                  : "text-[#4B5563] cursor-not-allowed"
            }`}
          >
            <span
              className={`w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                i < step
                  ? "bg-[#10B981] text-white"
                  : i === step
                    ? "bg-[rgba(16,185,129,0.3)] text-[#10B981]"
                    : "bg-[rgba(255,255,255,0.06)] text-[#4B5563]"
              }`}
            >
              {i < step ? <Check size={12} /> : i + 1}
            </span>
            {label}
          </button>
        ))}
      </div>

      {/* Step Content */}
      <div className="floating-card p-6">{renderStep()}</div>

      {/* Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
            step === 0
              ? "text-[#4B5563] cursor-not-allowed"
              : "text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.05)]"
          }`}
        >
          <ChevronLeft size={16} />
          Back
        </button>

        {step < STEPS.length - 1 ? (
          <button
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            disabled={!canProceed()}
            className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all ${
              canProceed()
                ? "bg-[#10B981] text-white hover:bg-[#0EA472]"
                : "bg-[rgba(16,185,129,0.2)] text-[#4B5563] cursor-not-allowed"
            }`}
          >
            Next
            <ChevronRight size={16} />
          </button>
        ) : (
          <button
            onClick={handleSubmit}
            disabled={submitting}
            className="flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium bg-[#10B981] text-white hover:bg-[#0EA472] transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Creating...
              </>
            ) : (
              <>
                <Check size={16} />
                Create Config
              </>
            )}
          </button>
        )}
      </div>
    </div>
  );
}
