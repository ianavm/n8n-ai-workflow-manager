"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import { useRouter } from "next/navigation";
import { Loader2, Plus, Search } from "lucide-react";

import { LeadCard } from "@/components/marketing/LeadCard";
import { PageHeader } from "@/components/portal/PageHeader";
import { Button } from "@/components/ui-shadcn/button";

interface Lead {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string | null;
  phone: string | null;
  company: string | null;
  source: string;
  score: number | null;
  stage: string;
  assigned_agent: string | null;
  tags: string[] | null;
  created_at: string;
}

const PIPELINE_STAGES = [
  { key: "new", label: "New", color: "#6B7280" },
  { key: "contacted", label: "Contacted", color: "#3B82F6" },
  { key: "qualified", label: "Qualified", color: "#F59E0B" },
  { key: "booked", label: "Booked", color: "#8B5CF6" },
  { key: "proposal", label: "Proposal", color: "#D97706" },
  { key: "won", label: "Won", color: "#10B981" },
  { key: "lost", label: "Lost", color: "#EF4444" },
] as const;

export default function LeadsPipelinePage() {
  const supabase = createClient();
  const router = useRouter();
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);

  const loadLeads = useCallback(async () => {
    setLoading(true);
    let query = supabase
      .from("mkt_leads")
      .select("*")
      .order("created_at", { ascending: false });

    if (search.trim()) {
      query = query.or(
        `first_name.ilike.%${search}%,last_name.ilike.%${search}%,email.ilike.%${search}%,company.ilike.%${search}%`
      );
    }

    const { data } = await query;
    setLeads(data ?? []);
    setLoading(false);
  }, [supabase, search]);

  useEffect(() => {
    loadLeads();
  }, [loadLeads]);

  function handleDragStart(e: React.DragEvent<HTMLDivElement>, leadId: string) {
    setDraggingId(leadId);
    e.dataTransfer.setData("text/plain", leadId);
    e.dataTransfer.effectAllowed = "move";
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }

  async function handleDrop(e: React.DragEvent<HTMLDivElement>, targetStage: string) {
    e.preventDefault();
    const leadId = e.dataTransfer.getData("text/plain");
    if (!leadId) return;

    const lead = leads.find((l) => l.id === leadId);
    if (!lead || lead.stage === targetStage) {
      setDraggingId(null);
      return;
    }

    // Optimistic update
    setLeads((prev) =>
      prev.map((l) => (l.id === leadId ? { ...l, stage: targetStage } : l))
    );
    setDraggingId(null);

    try {
      const res = await fetch(`/api/portal/marketing/leads/${leadId}/stage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage: targetStage }),
      });

      if (!res.ok) {
        // Revert on failure
        setLeads((prev) =>
          prev.map((l) => (l.id === leadId ? { ...l, stage: lead.stage } : l))
        );
      }
    } catch {
      // Revert on network error
      setLeads((prev) =>
        prev.map((l) => (l.id === leadId ? { ...l, stage: lead.stage } : l))
      );
    }
  }

  function getLeadsForStage(stageKey: string): Lead[] {
    return leads.filter((l) => l.stage === stageKey);
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        eyebrow="Marketing"
        title="Lead pipeline"
        description={`${leads.length} total leads across every stage.`}
        actions={
          <>
            <div className="relative">
              <Search
                className="size-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]"
                aria-hidden
              />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search leads..."
                className="h-9 pl-9 pr-3 rounded-[var(--radius-sm)] text-sm bg-[var(--input)] border border-[var(--border-subtle)] text-foreground placeholder:text-[var(--text-dim)] focus:outline-none focus:border-[var(--accent-teal)] w-56"
              />
            </div>
            <Button variant="default" size="md" onClick={() => setShowAddForm(true)}>
              <Plus className="size-4" />
              Add lead
            </Button>
          </>
        }
      />

      {/* Kanban Board */}
      {loading ? (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="size-6 animate-spin text-[var(--accent-teal)]" />
        </div>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-4 scrollbar-hide">
          {PIPELINE_STAGES.map((stage) => {
            const stageLeads = getLeadsForStage(stage.key);
            const isDropTarget = draggingId != null;

            return (
              <div
                key={stage.key}
                onDragOver={handleDragOver}
                onDrop={(e) => handleDrop(e, stage.key)}
                className="flex-shrink-0 w-64 flex flex-col rounded-xl"
                style={{
                  background: "rgba(255,255,255,0.02)",
                  border: isDropTarget
                    ? `1px dashed ${stage.color}40`
                    : "1px solid rgba(255,255,255,0.04)",
                  minHeight: 200,
                }}
              >
                {/* Stage Header */}
                <div
                  className="flex items-center justify-between px-3 py-2.5 rounded-t-xl"
                  style={{
                    borderBottom: `2px solid ${stage.color}`,
                  }}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: stage.color }}
                    />
                    <span className="text-sm font-medium text-white">
                      {stage.label}
                    </span>
                  </div>
                  <span
                    className="text-xs font-medium px-1.5 py-0.5 rounded"
                    style={{
                      color: stage.color,
                      backgroundColor: `${stage.color}1A`,
                    }}
                  >
                    {stageLeads.length}
                  </span>
                </div>

                {/* Cards */}
                <div className="flex-1 p-2 space-y-2 overflow-y-auto max-h-[calc(100vh-280px)]">
                  {stageLeads.length === 0 ? (
                    <div className="text-center py-6 text-xs text-[#6B7280]">
                      No leads
                    </div>
                  ) : (
                    stageLeads.map((lead) => (
                      <div
                        key={lead.id}
                        onClick={() =>
                          router.push(`/portal/marketing/leads/${lead.id}`)
                        }
                        className="cursor-pointer"
                      >
                        <LeadCard
                          lead={lead}
                          onDragStart={handleDragStart}
                        />
                      </div>
                    ))
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Quick Add Modal */}
      {showAddForm && (
        <QuickAddLeadModal
          onClose={() => setShowAddForm(false)}
          onCreated={() => {
            setShowAddForm(false);
            loadLeads();
          }}
        />
      )}
    </div>
  );
}

/* ---------------------------------------------------------------------- */
/* Inline Quick-Add Modal                                                  */
/* ---------------------------------------------------------------------- */

interface QuickAddLeadModalProps {
  onClose: () => void;
  onCreated: () => void;
}

function QuickAddLeadModal({ onClose, onCreated }: QuickAddLeadModalProps) {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [company, setCompany] = useState("");
  const [source, setSource] = useState("website");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch("/api/portal/marketing/leads", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          first_name: firstName.trim() || undefined,
          last_name: lastName.trim() || undefined,
          email: email.trim() || undefined,
          phone: phone.trim() || undefined,
          company: company.trim() || undefined,
          source,
        }),
      });

      if (!res.ok) {
        const body = await res.json();
        throw new Error(body.error ?? "Failed to create lead");
      }

      onCreated();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : "Failed to create lead";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  const SOURCE_OPTIONS = [
    "website",
    "google_ads",
    "meta_ads",
    "tiktok_ads",
    "linkedin_ads",
    "referral",
    "cold_outreach",
    "whatsapp",
    "phone",
    "email",
    "event",
    "partner",
    "organic",
    "other",
  ];

  const inputClasses =
    "w-full px-3 py-2 rounded-lg text-sm bg-[rgba(255,255,255,0.05)] border border-[rgba(255,255,255,0.08)] text-white placeholder:text-[#6B7280] focus:outline-none focus:border-[#10B981]";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-lg rounded-xl p-6 border"
        style={{
          background: "rgba(17,24,39,0.95)",
          borderColor: "rgba(255,255,255,0.08)",
          backdropFilter: "blur(20px)",
        }}
      >
        <h3 className="text-lg font-semibold text-white mb-5">Add Lead</h3>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
                First Name
              </label>
              <input
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="John"
                className={inputClasses}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
                Last Name
              </label>
              <input
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Doe"
                className={inputClasses}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="john@company.co.za"
              className={inputClasses}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
                Phone
              </label>
              <input
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+27 82 123 4567"
                className={inputClasses}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
                Company
              </label>
              <input
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="Acme Ltd"
                className={inputClasses}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-[#B0B8C8] mb-1.5">
              Source
            </label>
            <select
              value={source}
              onChange={(e) => setSource(e.target.value)}
              className={inputClasses}
            >
              {SOURCE_OPTIONS.map((s) => (
                <option key={s} value={s}>
                  {s.replace(/_/g, " ")}
                </option>
              ))}
            </select>
          </div>

          {error && <p className="text-xs text-red-400">{error}</p>}

          <div className="flex items-center justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-lg text-sm text-[#B0B8C8] hover:text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="px-4 py-2 rounded-lg text-sm font-medium text-white transition-all disabled:opacity-50"
              style={{
                background: "linear-gradient(135deg, #10B981, #059669)",
              }}
            >
              {submitting ? "Creating..." : "Create Lead"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
