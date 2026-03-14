"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/Badge";
import { format } from "date-fns";
import { useRouter } from "next/navigation";
import { Users, Search } from "lucide-react";

interface ClientSummary {
  id: string;
  full_name: string;
  email: string;
  company_name: string | null;
  status: string;
  last_login_at: string | null;
  active_workflows: number;
  messages_sent: number;
  messages_received: number;
  leads_created: number;
  total_crashes: number;
}

type FilterKey = "all" | "active" | "suspended" | "pending";

export default function ClientsPage() {
  const router = useRouter();
  const [clients, setClients] = useState<ClientSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<FilterKey>("all");

  useEffect(() => {
    async function fetchClients() {
      const res = await fetch("/api/admin/clients");
      if (res.ok) {
        setClients(await res.json());
      }
      setLoading(false);
    }
    fetchClients();
  }, []);

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

  // Find max messages for bar scaling
  const maxMessages = Math.max(
    ...clients.map((c) => c.messages_sent + c.messages_received),
    1
  );
  const maxLeads = Math.max(...clients.map((c) => c.leads_created), 1);

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
            <p className="text-sm text-[#B0B8C8] mt-2">
              {clients.length} {clients.length === 1 ? "client" : "clients"} registered
            </p>
          </div>
        </div>
        <div className="relative max-w-xs w-full">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
          <input
            type="text"
            placeholder="Search clients..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="max-w-xs pl-9"
          />
        </div>
      </div>

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
          <Users size={32} className="text-[#6B7280] mx-auto mb-3 opacity-50" />
          <p className="text-sm text-[#6B7280]">
            {search ? "No clients match your search" : "No clients yet"}
          </p>
        </div>
      ) : (
        <div className="client-card-grid">
          {filtered.map((c, idx) => (
            <div
              key={c.id}
              className={`floating-card p-6 cursor-pointer animate-fade-in-up ${
                c.total_crashes > 0 ? "" : ""
              }`}
              style={{
                animationDelay: `${Math.min(idx * 0.06, 0.5)}s`,
                borderLeft: c.total_crashes > 0 ? "3px solid rgba(239,68,68,0.5)" : undefined,
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
                  <div className="text-xs text-[#6B7280] truncate">{c.email}</div>
                  {c.company_name && (
                    <div className="text-xs text-[#6B7280] truncate">{c.company_name}</div>
                  )}
                </div>
                <Badge variant={statusVariant(c.status)}>{c.status}</Badge>
              </div>

              {/* Gradient divider */}
              <div className="gdiv" />

              {/* Mini metrics */}
              <div className="mini-metrics mt-3">
                <div>
                  <div className="text-lg font-bold text-white">{c.active_workflows}</div>
                  <div className="text-[11px] text-[#6B7280] uppercase mt-0.5">Workflows</div>
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
                    {(c.messages_sent + c.messages_received).toLocaleString()}
                  </div>
                  <div className="text-[11px] text-[#6B7280] uppercase mt-0.5">Messages</div>
                  <div className="mini-bar">
                    <div
                      className="mini-bar-fill"
                      style={{
                        width: `${((c.messages_sent + c.messages_received) / maxMessages) * 100}%`,
                        background: "#6C63FF",
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="text-lg font-bold text-white">{c.leads_created}</div>
                  <div className="text-[11px] text-[#6B7280] uppercase mt-0.5">Leads</div>
                  <div className="mini-bar">
                    <div
                      className="mini-bar-fill"
                      style={{
                        width: `${(c.leads_created / maxLeads) * 100}%`,
                        background: "#00D4AA",
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className={`text-lg font-bold ${c.total_crashes > 0 ? "text-[#EF4444]" : "text-white"}`}>
                    {c.total_crashes}
                  </div>
                  <div className="text-[11px] text-[#6B7280] uppercase mt-0.5">Crashes</div>
                  <div className="mini-bar">
                    <div
                      className="mini-bar-fill"
                      style={{
                        width: `${Math.min(c.total_crashes * 10, 100)}%`,
                        background: "#EF4444",
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Footer */}
              <div className="flex items-center justify-between mt-4">
                <span className="text-[11px] text-[#6B7280]">
                  Last: {c.last_login_at ? format(new Date(c.last_login_at), "MMM d, yyyy") : "Never"}
                </span>
                <span className="text-xs text-[#6C63FF]">View Details &rarr;</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
