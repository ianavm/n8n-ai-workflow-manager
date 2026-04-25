"use client";

import { useCallback, useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { format } from "date-fns";
import { useRouter } from "next/navigation";
import { Users, Search, Plus, Settings2 } from "lucide-react";
import { Button } from "@/components/ui-shadcn/button";
import { CreateOrganizationDialog } from "@/components/admin/CreateOrganizationDialog";
import { AdjustSeatsDialog } from "@/components/admin/AdjustSeatsDialog";
import { toast } from "sonner";

interface ClientSummary {
  id: string;
  full_name: string;
  email: string;
  company_name: string | null;
  status: string;
  last_login_at: string | null;
  active_workflows: number;
  messages_sent: number | null;
  messages_received: number | null;
  leads_created: number | null;
  total_crashes: number | null;
  total_members?: number;
  manager_count?: number;
  employee_count?: number;
  seat_limit?: number;
  business_data_redacted?: boolean;
}

type FilterKey = "all" | "active" | "suspended" | "pending";

export default function ClientsPage() {
  const router = useRouter();
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [seatsTarget, setSeatsTarget] = useState<ClientSummary | null>(null);

  const fetchClients = useCallback(async () => {
    const res = await fetch("/api/admin/clients");
    if (res.ok) {
      setClients(await res.json());
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchClients();
  }, [fetchClients]);

  const filtered = clients
    .filter((c) => {
      if (filter !== "all" && c.status !== filter) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        c.full_name.toLowerCase().includes(q) ||
        c.email.toLowerCase().includes(q) ||
        (c.company_name || "").toLowerCase().includes(q)
      );
    });

  const counts = {
    all: clients.length,
    active: clients.filter((c) => c.status === "active").length,
    suspended: clients.filter((c) => c.status === "suspended").length,
    pending: clients.filter((c) => c.status !== "active" && c.status !== "suspended").length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#6C63FF] border-t-transparent rounded-full" />
      </div>
    );
  }

  const statusVariant = (s: string) =>
    s === "active" ? "success" : s === "suspended" ? "danger" : "warning";

  // Find max messages for bar scaling. Skip null (POPIA-redacted) entries.
  const maxMessages = Math.max(
    ...clients.map((c) => (c.messages_sent ?? 0) + (c.messages_received ?? 0)),
    1
  );
  const maxLeads = Math.max(...clients.map((c) => c.leads_created ?? 0), 1);
  const popiaRedacted = clients[0]?.business_data_redacted === true;

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="relative">
          <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
          <div className="relative">
            <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
              All <span className="gradient-text">Clients</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-2">
              {clients.length} {clients.length === 1 ? "client" : "clients"} registered
              {popiaRedacted ? (
                <span className="ml-2 inline-flex items-center gap-1 rounded-full border border-[color-mix(in_srgb,var(--accent-purple)_30%,transparent)] bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-[var(--accent-purple)]">
                  POPIA · Business data hidden
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:max-w-xs">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-dim)]" />
            <input
              type="text"
              placeholder="Search clients..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9"
            />
          </div>
          <Button onClick={() => setCreateOpen(true)} className="shrink-0">
            <Plus className="size-4" aria-hidden />
            <span>New org</span>
          </Button>
        </div>
      </div>

      <CreateOrganizationDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        onCreated={(org) => {
          toast.success(`${org.company_name} created`, {
            description: `Invite sent to ${org.manager_email}`,
          });
          fetchClients();
        }}
      />

      {/* Filter Pills */}
      <div className="filter-pills">
        {(["all", "active", "suspended", "pending"] as FilterKey[]).map((key) => (
          <button
            key={key}
            className={`filter-pill ${filter === key ? "active" : ""}`}
            onClick={() => setFilter(key)}
          >
            {key.charAt(0).toUpperCase() + key.slice(1)} ({counts[key]})
          </button>
        ))}
      </div>

      {/* Client Card Grid */}
      {filtered.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Users size={32} className="text-[var(--text-dim)] mx-auto mb-3 opacity-50" />
          <p className="text-sm text-[var(--text-dim)]">
            {search ? "No clients match your search" : "No clients yet"}
          </p>
        </div>
      ) : (
        <div className="client-card-grid">
          {filtered.map((c, idx) => (
            <div
              key={c.id}
              className="floating-card p-6 cursor-pointer animate-fade-in-up"
              style={{
                animationDelay: `${Math.min(idx * 0.06, 0.5)}s`,
                borderLeft: (c.total_crashes ?? 0) > 0 ? "3px solid rgba(239,68,68,0.5)" : undefined,
              }}
              onClick={() => router.push(`/admin/clients/${c.id}`)}
            >
              {/* Client header */}
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-11 h-11 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                  style={{
                    background: `linear-gradient(135deg, #6C63FF, #00D4AA)`,
                  }}
                >
                  {c.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="text-sm font-semibold text-white truncate">{c.full_name}</div>
                  <div className="text-xs text-[var(--text-dim)] truncate">{c.email}</div>
                  {c.company_name && (
                    <div className="text-xs text-[var(--text-dim)] truncate">{c.company_name}</div>
                  )}
                </div>
                <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
              </div>

              {/* Gradient divider */}
              <div className="gdiv" />

              {/* Mini metrics — superior_admin sees membership counts (POPIA-safe);
                   staff_admin sees business stats. */}
              <div className="mini-metrics mt-3">
                {c.business_data_redacted ? (
                  <>
                    <div>
                      <div className="text-lg font-bold text-white">{c.total_members ?? 0}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Members</div>
                      <div className="mini-bar">
                        <div
                          className="mini-bar-fill"
                          style={{
                            width: `${Math.min(((c.total_members ?? 0) / Math.max(c.seat_limit ?? 5, 1)) * 100, 100)}%`,
                            background: "#6C63FF",
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-white">{c.manager_count ?? 0}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Managers</div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-white">{c.employee_count ?? 0}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Employees</div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-white">{c.active_workflows}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Workflows</div>
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <div className="text-lg font-bold text-white">{c.active_workflows}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Workflows</div>
                      <div className="mini-bar">
                        <div
                          className="mini-bar-fill"
                          style={{
                            width: `${Math.min((c.active_workflows / 10) * 100, 100)}%`,
                            background: "#6C63FF",
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-white">
                        {((c.messages_sent ?? 0) + (c.messages_received ?? 0)).toLocaleString()}
                      </div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Messages</div>
                      <div className="mini-bar">
                        <div
                          className="mini-bar-fill"
                          style={{
                            width: `${(((c.messages_sent ?? 0) + (c.messages_received ?? 0)) / maxMessages) * 100}%`,
                            background: "#6C63FF",
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className="text-lg font-bold text-white">{c.leads_created ?? 0}</div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Leads</div>
                      <div className="mini-bar">
                        <div
                          className="mini-bar-fill"
                          style={{
                            width: `${((c.leads_created ?? 0) / maxLeads) * 100}%`,
                            background: "#00D4AA",
                          }}
                        />
                      </div>
                    </div>
                    <div>
                      <div className={`text-lg font-bold ${(c.total_crashes ?? 0) > 0 ? "text-[#EF4444]" : "text-white"}`}>
                        {c.total_crashes ?? 0}
                      </div>
                      <div className="text-[11px] text-[var(--text-dim)] uppercase mt-0.5">Crashes</div>
                      <div className="mini-bar">
                        <div
                          className="mini-bar-fill"
                          style={{
                            width: `${Math.min((c.total_crashes ?? 0) * 10, 100)}%`,
                            background: "#EF4444",
                          }}
                        />
                      </div>
                    </div>
                  </>
                )}
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between mt-4 gap-2">
                <span className="text-[11px] text-[var(--text-dim)]">
                  {c.seat_limit ? (
                    <>
                      <span className="text-foreground font-medium">{c.total_members ?? 1}</span>
                      <span className="text-[var(--text-dim)]">/{c.seat_limit} seats</span>
                    </>
                  ) : (
                    <>Last: {c.last_login_at ? format(new Date(c.last_login_at), "MMM d, yyyy") : "Never"}</>
                  )}
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSeatsTarget(c);
                    }}
                    className="text-[11px] text-[var(--text-dim)] hover:text-foreground inline-flex items-center gap-1 transition-colors"
                    title="Adjust seat limit"
                  >
                    <Settings2 className="size-3" aria-hidden />
                    Seats
                  </button>
                  <span className="text-xs text-[#6C63FF]">View &rarr;</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <AdjustSeatsDialog
        open={seatsTarget !== null}
        onOpenChange={(o) => {
          if (!o) setSeatsTarget(null);
        }}
        org={
          seatsTarget
            ? {
                id: seatsTarget.id,
                company_name: seatsTarget.company_name,
                seat_limit: seatsTarget.seat_limit ?? 5,
                seats_used: seatsTarget.total_members ?? 1,
              }
            : null
        }
        onUpdated={(newLimit) => {
          toast.success(`Seat limit updated to ${newLimit}`);
          fetchClients();
        }}
      />
    </div>
  );
}
