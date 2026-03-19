"use client";

import { useEffect, useState } from "react";
import { Card } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  HeadphonesIcon,
  Plus,
  Send,
  CheckCircle,
  Clock,
  MessageSquare,
} from "lucide-react";

interface Ticket {
  id: string;
  ticket_id: string;
  subject: string;
  priority: string;
  status: string;
  ai_summary: string | null;
  created_at: string;
  resolved_at: string | null;
}

export default function PortalSupportPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({ subject: "", body: "" });

  useEffect(() => {
    fetchTickets();
  }, []);

  async function fetchTickets() {
    try {
      const res = await fetch("/api/portal/support");
      if (res.ok) {
        setTickets(await res.json());
      }
    } catch {
      toast.error("Failed to load tickets");
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!form.subject.trim()) return;

    setSubmitting(true);
    try {
      const res = await fetch("/api/portal/support", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });

      if (res.ok) {
        toast.success("Support ticket created! Our AI will analyze it shortly.");
        setForm({ subject: "", body: "" });
        setShowForm(false);
        fetchTickets();
      } else {
        toast.error("Failed to create ticket");
      }
    } catch {
      toast.error("Network error");
    } finally {
      setSubmitting(false);
    }
  }

  const openCount = tickets.filter((t) => t.status === "Open" || t.status === "In_Progress").length;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#6C63FF]" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-3xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <HeadphonesIcon className="text-[#6C63FF]" size={28} />
            Support
          </h1>
          <p className="text-[#6B7280] mt-1">
            {openCount > 0
              ? `You have ${openCount} open ticket${openCount > 1 ? "s" : ""}`
              : "Need help? Create a support ticket below."}
          </p>
        </div>
        <Button onClick={() => setShowForm(!showForm)} className="flex items-center gap-2">
          <Plus size={16} />
          New Ticket
        </Button>
      </div>

      {/* New Ticket Form */}
      {showForm && (
        <Card className="p-6">
          <h2 className="text-sm font-semibold text-white mb-4">Create Support Ticket</h2>
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="text-xs text-[#6B7280] block mb-1">Subject</label>
              <Input
                value={form.subject}
                onChange={(e) => setForm({ ...form, subject: e.target.value })}
                placeholder="Brief description of the issue"
                required
              />
            </div>
            <div>
              <label className="text-xs text-[#6B7280] block mb-1">Details</label>
              <textarea
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                placeholder="Describe the issue in detail. Include any error messages, steps to reproduce, etc."
                className="w-full px-3 py-2 bg-[rgba(255,255,255,0.03)] border border-[rgba(255,255,255,0.06)] rounded-lg text-sm text-white placeholder-[#6B7280] focus:outline-none focus:border-[#6C63FF]/40 min-h-[120px] resize-y"
              />
            </div>
            <div className="flex justify-end gap-3">
              <Button type="button" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={submitting} className="flex items-center gap-2">
                <Send size={14} />
                {submitting ? "Submitting..." : "Submit Ticket"}
              </Button>
            </div>
          </form>
        </Card>
      )}

      {/* Ticket List */}
      {tickets.length > 0 ? (
        <div className="space-y-4">
          {tickets.map((ticket) => (
            <Card key={ticket.id} className="p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <MessageSquare size={14} className="text-[#6C63FF] shrink-0" />
                    <h3 className="text-sm font-medium text-white truncate">{ticket.subject}</h3>
                  </div>
                  {ticket.ai_summary && (
                    <p className="text-xs text-[#9CA3AF] mt-1">{ticket.ai_summary}</p>
                  )}
                  <p className="text-[10px] text-[#6B7280] mt-2">
                    Created {formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })}
                    {ticket.resolved_at && (
                      <> &middot; Resolved {formatDistanceToNow(new Date(ticket.resolved_at), { addSuffix: true })}</>
                    )}
                  </p>
                </div>
                <Badge
                  variant={
                    ticket.status === "Resolved" || ticket.status === "Closed"
                      ? "success"
                      : ticket.status === "Open"
                      ? "danger"
                      : "warning"
                  }
                >
                  {ticket.status === "Resolved" ? (
                    <span className="flex items-center gap-1"><CheckCircle size={10} /> Resolved</span>
                  ) : ticket.status === "Open" ? (
                    <span className="flex items-center gap-1"><Clock size={10} /> Open</span>
                  ) : (
                    ticket.status.replace("_", " ")
                  )}
                </Badge>
              </div>
            </Card>
          ))}
        </div>
      ) : (
        !showForm && (
          <EmptyState
            icon={<CheckCircle size={48} />}
            title="No support tickets"
            description="You haven't created any support tickets yet. Click 'New Ticket' above if you need help."
          />
        )
      )}
    </div>
  );
}
