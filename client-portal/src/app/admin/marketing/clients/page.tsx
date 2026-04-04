"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Search, Plus, Loader2 } from "lucide-react";

interface ConfigRow {
  id: string;
  client_id: string;
  platforms_enabled: string[];
  budget_monthly_cap: number;
  lead_assignment_mode: string;
  modules_enabled: Record<string, boolean>;
  created_at: string;
  clients: { full_name: string; email: string } | null;
}

function formatZAR(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  })}`;
}

const PLATFORM_LABELS: Record<string, string> = {
  google_ads: "Google",
  meta_ads: "Meta",
  tiktok_ads: "TikTok",
  linkedin_ads: "LinkedIn",
  blotato: "Blotato",
};

export default function MarketingClientsPage() {
  const [configs, setConfigs] = useState<ConfigRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const res = await fetch("/api/admin/marketing/config");
      if (!res.ok) {
        throw new Error("Failed to load configs");
      }
      const json = await res.json();
      setConfigs(json.data ?? []);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const filtered = configs.filter((c) => {
    if (!search) return true;
    const name = c.clients?.full_name?.toLowerCase() ?? "";
    const email = c.clients?.email?.toLowerCase() ?? "";
    const q = search.toLowerCase();
    return name.includes(q) || email.includes(q);
  });

  if (error) {
    return (
      <div className="floating-card p-6 text-center">
        <p className="text-red-400">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Marketing Clients</h1>
          <p className="text-sm text-[#B0B8C8] mt-1">
            {configs.length} client{configs.length !== 1 ? "s" : ""} with marketing configured
          </p>
        </div>
        <Link
          href="/admin/marketing/onboarding"
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-[#10B981] text-white hover:bg-[#0EA472] transition-all"
        >
          <Plus size={16} />
          Onboard Client
        </Link>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search
          size={16}
          className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]"
        />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search clients..."
          className="w-full pl-9 pr-3 py-2 rounded-lg bg-[rgba(255,255,255,0.04)] border border-[rgba(255,255,255,0.08)] text-white text-sm placeholder-[#4B5563] focus:outline-none focus:border-[rgba(16,185,129,0.5)]"
        />
      </div>

      {/* Client Cards */}
      {loading ? (
        <div className="flex items-center justify-center py-12 text-[#6B7280]">
          <Loader2 size={20} className="animate-spin mr-2" />
          Loading clients...
        </div>
      ) : filtered.length === 0 ? (
        <div className="floating-card p-8 text-center">
          <p className="text-[#6B7280]">
            {search
              ? "No clients match your search."
              : "No marketing clients configured yet."}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {filtered.map((cfg) => (
            <Link
              key={cfg.id}
              href={`/admin/marketing/clients/${cfg.client_id}`}
              className="floating-card p-5 hover:bg-[rgba(255,255,255,0.03)] transition-colors group"
            >
              <div className="flex items-start justify-between mb-3">
                <div>
                  <p className="text-sm font-medium text-white group-hover:text-[#10B981] transition-colors">
                    {cfg.clients?.full_name ?? "Unknown"}
                  </p>
                  <p className="text-xs text-[#6B7280]">
                    {cfg.clients?.email ?? ""}
                  </p>
                </div>
                <span className="text-xs text-[#6B7280]">
                  {new Date(cfg.created_at).toLocaleDateString("en-ZA")}
                </span>
              </div>

              {/* Platforms */}
              <div className="flex flex-wrap gap-1.5 mb-3">
                {cfg.platforms_enabled.map((p) => (
                  <span
                    key={p}
                    className="px-2 py-0.5 rounded text-[10px] font-medium bg-[rgba(16,185,129,0.08)] text-[#10B981]"
                  >
                    {PLATFORM_LABELS[p] ?? p}
                  </span>
                ))}
              </div>

              {/* Details */}
              <div className="flex items-center gap-4 text-xs text-[#6B7280]">
                <span>
                  Budget:{" "}
                  {cfg.budget_monthly_cap > 0
                    ? formatZAR(cfg.budget_monthly_cap)
                    : "No cap"}
                </span>
                <span className="capitalize">
                  {cfg.lead_assignment_mode.replace(/_/g, " ")}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
