"use client";

import { useEffect, useState } from "react";
import { formatDistanceToNow } from "date-fns";
import { toast } from "sonner";
import {
  CheckCircle,
  Clock,
  HeadphonesIcon,
  MessageSquare,
  Plus,
  Send,
} from "lucide-react";

import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import { Field } from "@/components/ui-shadcn/field";
import { Input } from "@/components/ui-shadcn/input";
import { Textarea } from "@/components/ui-shadcn/textarea";

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

function ticketBadgeTone(status: string): "success" | "danger" | "warning" | "neutral" {
  if (status === "Resolved" || status === "Closed") return "success";
  if (status === "Open") return "danger";
  if (status === "In_Progress") return "warning";
  return "neutral";
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
      if (res.ok) setTickets(await res.json());
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

  return (
    <div className="flex flex-col gap-8 max-w-3xl">
      <PageHeader
        eyebrow="Support"
        title="Support tickets"
        description={
          loading
            ? "Loading…"
            : openCount > 0
              ? `You have ${openCount} open ticket${openCount > 1 ? "s" : ""}.`
              : "Need help? Create a support ticket below."
        }
        actions={
          <Button
            variant={showForm ? "outline" : "default"}
            size="md"
            onClick={() => setShowForm((v) => !v)}
          >
            <Plus className="size-4" />
            {showForm ? "Cancel" : "New ticket"}
          </Button>
        }
      />

      {/* New ticket form */}
      {showForm ? (
        <Card variant="default" accent="gradient-static" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Create a support ticket</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <form onSubmit={handleSubmit} className="flex flex-col gap-5">
              <Field label="Subject" required>
                <Input
                  value={form.subject}
                  onChange={(e) => setForm({ ...form, subject: e.target.value })}
                  placeholder="Brief description of the issue"
                  required
                />
              </Field>
              <Field label="Details" hint="Include error messages, steps to reproduce, or screenshots if possible.">
                <Textarea
                  value={form.body}
                  onChange={(e) => setForm({ ...form, body: e.target.value })}
                  placeholder="Describe the issue in detail…"
                />
              </Field>
              <div className="flex justify-end gap-3">
                <Button type="button" variant="outline" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="default" loading={submitting}>
                  <Send className="size-4" />
                  Submit ticket
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      {/* Ticket list */}
      {loading ? (
        <LoadingState variant="list" rows={4} />
      ) : tickets.length > 0 ? (
        <ul className="flex flex-col gap-3">
          {tickets.map((ticket) => {
            const tone = ticketBadgeTone(ticket.status);
            return (
              <li key={ticket.id}>
                <Card variant="default" padding="md">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1.5">
                        <MessageSquare className="size-3.5 text-[var(--accent-purple)] shrink-0" aria-hidden />
                        <h3 className="text-sm font-semibold text-foreground truncate">
                          {ticket.subject}
                        </h3>
                      </div>
                      {ticket.ai_summary ? (
                        <p className="text-xs text-[var(--text-muted)] mt-1 leading-relaxed">
                          {ticket.ai_summary}
                        </p>
                      ) : null}
                      <p className="text-[11px] text-[var(--text-dim)] mt-2">
                        Created {formatDistanceToNow(new Date(ticket.created_at), { addSuffix: true })}
                        {ticket.resolved_at ? (
                          <> · Resolved {formatDistanceToNow(new Date(ticket.resolved_at), { addSuffix: true })}</>
                        ) : null}
                      </p>
                    </div>
                    <Badge tone={tone} appearance="soft" size="sm" className="shrink-0">
                      {ticket.status === "Resolved" ? (
                        <>
                          <CheckCircle className="size-3" /> Resolved
                        </>
                      ) : ticket.status === "Open" ? (
                        <>
                          <Clock className="size-3" /> Open
                        </>
                      ) : (
                        ticket.status.replace("_", " ")
                      )}
                    </Badge>
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      ) : !showForm ? (
        <EmptyState
          icon={<HeadphonesIcon className="size-5" />}
          title="No support tickets"
          description="You haven't created any support tickets yet. Click &ldquo;New ticket&rdquo; above if you need help."
        />
      ) : null}
    </div>
  );
}
