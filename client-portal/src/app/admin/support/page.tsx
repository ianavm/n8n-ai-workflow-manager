"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  HeadphonesIcon,
  Clock,
  CheckCircle,
  AlertTriangle,
  Search,
  Filter,
} from "lucide-react";

interface Ticket {
  id: string;
  ticket_id: string;
  client_email: string;
  subject: string;
  department: string;
  priority: "P1" | "P2" | "P3" | "P4";
  status: "Open" | "In_Progress" | "Waiting" | "Resolved" | "Closed";
  ai_summary: string | null;
  ai_suggested_resolution: string | null;
  sla_due_at: string | null;
  created_at: string;
  resolved_at: string | null;
}

const priorityConfig = {
  P1: { color: "text-red-400 bg-red-500/10 border-red-500/20", label: "Critical" },
  P2: { color: "text-orange-400 bg-orange-500/10 border-orange-500/20", label: "High" },
  P3: { color: "text-yellow-400 bg-yellow-500/10 border-yellow-500/20", label: "Medium" },
  P4: { color: "text-blue-400 bg-blue-500/10 border-blue-500/20", label: "Low" },
};

const statusConfig = {
  Open: "danger",
  In_Progress: "warning",
  Waiting: "default",
  Resolved: "success",
  Closed: "default",
} as const;

export default function AdminSupportPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  useEffect(() => {
    async function fetchTickets() {
      try {
        const res = await fetch("/api/admin/support");
        if (res.ok) {
          setTickets(await res.json());
        }
      } catch {
        toast.error("Failed to load tickets");
      } finally {
        setLoading(false);
      }
    }
    fetchTickets();
    const interval = setInterval(fetchTickets, 30000);
    return () => clearInterval(interval);
  }, []);

  const filteredTickets = tickets.filter((t) => {
    if (filter !== "all" && t.status !== filter) return false;
    if (search && !t.subject.toLowerCase().includes(search.toLowerCase()) && !t.client_email.toLowerCase().includes(search.toLowerCase())) return false;
    return true;
  });

  const openCount = tickets.filter((t) => t.status === "Open").length;
  const inProgressCount = tickets.filter((t) => t.status === "In_Progress").length;
  const resolvedToday = tickets.filter(
    (t) => t.status === "Resolved" && t.resolved_at && new Date(t.resolved_at).toDateString() === new Date().toDateString()
  ).length;
  const slaBreach = tickets.filter(
    (t) => t.sla_due_at && new Date(t.sla_due_at) < new Date() && t.status !== "Resolved" && t.status !== "Closed"
  ).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#6C63FF]" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <HeadphonesIcon className="text-[#6C63FF]" size={28} />
          Support Tickets
        </h1>
        <p className="text-[#6B7280] mt-1">AI-powered ticket management and SLA monitoring</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${openCount > 0 ? "text-red-400" : "text-[#6B7280]"}`}>{openCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">Open</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-yellow-400">{inProgressCount}</div>
          <div className="text-xs text-[#6B7280] mt-1">In Progress</div>
        </Card>
        <Card className="p-4 text-center">
          <div className="text-2xl font-bold text-emerald-400">{resolvedToday}</div>
          <div className="text-xs text-[#6B7280] mt-1">Resolved Today</div>
        </Card>
        <Card className="p-4 text-center">
          <div className={`text-2xl font-bold ${slaBreach > 0 ? "text-red-400 animate-pulse" : "text-[#6B7280]"}`}>{slaBreach}</div>
          <div className="text-xs text-[#6B7280] mt-1">SLA Breached</div>
        </Card>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#6B7280]" />
          <input
            type="text"
            placeholder="Search tickets..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-white placeholder-[#6B7280] focus:outline-none focus:border-[#6C63FF]/40"
          />
        </div>
        <div className="flex items-center gap-1">
          {["all", "Open", "In_Progress", "Waiting", "Resolved"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-[#6C63FF]/20 text-[#6C63FF]"
                  : "text-[#6B7280] hover:text-white hover:bg-[rgba(255,255,255,0.03)]"
              }`}
            >
              {f === "all" ? "All" : f.replace("_", " ")}
            </button>
          ))}
        </div>
      </div>

      {/* Ticket List */}
      {filteredTickets.length > 0 ? (
        <Card className="divide-y divide-[rgba(255,255,255,0.06)]">
          {filteredTickets.map((ticket) => {
            const prio = priorityConfig[ticket.priority];
            const isBreached = ticket.sla_due_at && new Date(ticket.sla_due_at) < new Date() && ticket.status !== "Resolved" && ticket.status !== "Closed";
            return (
              <div key={ticket.id} className={`p-4 ${isBreached ? "bg-red-500/5" : ""}`}>
                <div className="flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold border ${prio.color}`}>
                        {ticket.priority}
                      </span>
                      <h3 className="text-sm font-medium text-white truncate">{ticket.subject}</h3>
                    </div>
                    <p className="text-xs text-[#6B7280]">{ticket.client_email}</p>
                    {ticket.ai_summary && (
                      <p className="text-xs text-[#9CA3AF] mt-1 line-clamp-2">{ticket.ai_summary}</p>
                    )}
                    {ticket.ai_suggested_resolution && (
                      <p className="text-xs text-[#6C63FF] mt-1">AI Suggestion: {ticket.ai_suggested_resolution}</p>
                    )}
                  </div>
                  <div className="text-right shrink-0">
                    <Badge variant={statusConfig[ticket.status] || "default"}>
                      {ticket.status.replace("_", " ")}
                    </Badge>
                    <p className="text-[10px] text-[#6B7280] mt-1">
                      {formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })}
                    </p>
                    {isBreached && (
                      <p className="text-[10px] text-red-400 mt-0.5 flex items-center justify-end gap-1">
                        <AlertTriangle size={10} /> SLA Breached
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </Card>
      ) : (
        <EmptyState
          icon={<CheckCircle size={48} />}
          title="No tickets found"
          description={filter !== "all" ? "No tickets match the current filter." : "No support tickets yet. The system will create tickets automatically when issues are detected."}
        />
      )}
    </div>
  );
}
