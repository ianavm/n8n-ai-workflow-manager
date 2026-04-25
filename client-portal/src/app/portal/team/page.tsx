"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { format } from "date-fns";
import {
  ArrowDownToLine,
  ArrowUpFromLine,
  MoreHorizontal,
  Pause,
  Play,
  ShieldCheck,
  Trash2,
  UserPlus,
  Users,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui-shadcn/button";
import { Badge } from "@/components/ui-shadcn/badge";
import { Card } from "@/components/ui-shadcn/card";
import { Skeleton } from "@/components/ui-shadcn/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui-shadcn/table";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui-shadcn/dropdown-menu";
import { useMember } from "@/lib/providers/MemberProvider";
import { InviteEmployeeDialog } from "@/components/portal/team/InviteEmployeeDialog";

interface TeamMember {
  id: string;
  email: string;
  full_name: string | null;
  role: "manager" | "employee";
  status: "active" | "invited" | "suspended";
  manager_id: string | null;
  invited_at: string | null;
  joined_at: string | null;
  last_login_at: string | null;
  created_at: string;
}

interface TeamResponse {
  members: TeamMember[];
  seat_limit: number;
  seats_used: number;
  company_name: string;
  can_manage: boolean;
}

const STATUS_TONE: Record<TeamMember["status"], "success" | "warning" | "danger"> = {
  active: "success",
  invited: "warning",
  suspended: "danger",
};

export default function TeamPage() {
  const router = useRouter();
  const { memberId, memberRole, loading: memberLoading, refresh } = useMember();
  const [data, setData] = useState<TeamResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [pendingId, setPendingId] = useState<string | null>(null);

  const fetchTeam = useCallback(async () => {
    const res = await fetch("/api/portal/team");
    if (res.ok) {
      const payload: TeamResponse = await res.json();
      setData(payload);
    } else if (res.status === 401) {
      router.push("/portal/login");
    }
    setLoading(false);
  }, [router]);

  useEffect(() => {
    fetchTeam();
  }, [fetchTeam]);

  // Redirect non-members (admins shouldn't be here either).
  useEffect(() => {
    if (!memberLoading && !memberRole) {
      router.replace("/portal");
    }
  }, [memberLoading, memberRole, router]);

  async function patchMember(id: string, body: Partial<{ role: "manager" | "employee"; status: "active" | "suspended" }>) {
    setPendingId(id);
    try {
      const res = await fetch(`/api/portal/team/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(payload?.error ?? "Update failed");
        return;
      }
      toast.success("Member updated");
      await Promise.all([fetchTeam(), refresh()]);
    } finally {
      setPendingId(null);
    }
  }

  async function removeMember(id: string) {
    if (!confirm("Remove this member from your team? They lose access immediately.")) return;
    setPendingId(id);
    try {
      const res = await fetch(`/api/portal/team/${id}`, { method: "DELETE" });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        toast.error(payload?.error ?? "Remove failed");
        return;
      }
      toast.success("Member removed");
      await Promise.all([fetchTeam(), refresh()]);
    } finally {
      setPendingId(null);
    }
  }

  if (loading || memberLoading) {
    return (
      <div className="flex flex-col gap-6 max-w-[1200px]">
        <Skeleton className="h-12 w-64" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (!data) {
    return (
      <Card className="p-12 text-center max-w-[1200px]">
        <Users className="size-8 text-[var(--text-dim)] mx-auto mb-3" />
        <p className="text-sm text-[var(--text-muted)]">Could not load team.</p>
      </Card>
    );
  }

  const seatsRemaining = Math.max(0, data.seat_limit - data.seats_used);
  const canManage = data.can_manage;

  return (
    <div className="flex flex-col gap-6 max-w-[1200px]">
      <header className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--brand-primary)] mb-2">
            Account · Team
          </p>
          <h1 className="text-3xl lg:text-4xl font-bold tracking-tight">
            <span className="gradient-text">{data.company_name || "Your team"}</span>
          </h1>
          <p className="text-sm text-[var(--text-muted)] mt-2">
            Manage who can sign in to your portal.
          </p>
        </div>
        {canManage ? (
          <Button onClick={() => setInviteOpen(true)} disabled={seatsRemaining <= 0}>
            <UserPlus className="size-4" aria-hidden />
            <span>Invite member</span>
          </Button>
        ) : null}
      </header>

      {/* Seat usage */}
      <Card className="p-5">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.12em] text-[var(--text-dim)] font-semibold">
              Seats
            </p>
            <p className="mt-1 text-2xl font-bold">
              {data.seats_used}{" "}
              <span className="text-sm font-medium text-[var(--text-muted)]">
                / {data.seat_limit}
              </span>
            </p>
          </div>
          <div className="flex-1 sm:max-w-xs">
            <div className="h-2 rounded-full bg-[var(--bg-inset)] overflow-hidden">
              <div
                className="h-full rounded-full bg-[image:var(--brand-gradient)] transition-[width] duration-[var(--dur-med)]"
                style={{
                  width: `${Math.min(100, (data.seats_used / Math.max(1, data.seat_limit)) * 100)}%`,
                }}
              />
            </div>
            <p className="mt-2 text-xs text-[var(--text-dim)]">
              {seatsRemaining === 0
                ? "Limit reached. Contact AnyVision to add seats."
                : `${seatsRemaining} ${seatsRemaining === 1 ? "seat" : "seats"} available.`}
            </p>
          </div>
        </div>
      </Card>

      {/* Members table */}
      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Role</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Last login</TableHead>
              {canManage ? <TableHead className="text-right">Actions</TableHead> : null}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.members.map((m) => {
              const isSelf = m.id === memberId;
              const isManager = m.role === "manager";
              return (
                <TableRow key={m.id}>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">
                        {m.full_name || "—"}
                      </span>
                      {isSelf ? (
                        <Badge tone="info" appearance="soft">
                          You
                        </Badge>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="text-[var(--text-muted)]">{m.email}</TableCell>
                  <TableCell>
                    <Badge tone={isManager ? "info" : "neutral"} appearance="soft">
                      {isManager ? (
                        <span className="inline-flex items-center gap-1">
                          <ShieldCheck className="size-3" aria-hidden />
                          Manager
                        </span>
                      ) : (
                        "Employee"
                      )}
                    </Badge>
                  </TableCell>
                  <TableCell>
                    <Badge tone={STATUS_TONE[m.status]} appearance="soft">
                      {m.status}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-[var(--text-muted)] text-sm">
                    {m.last_login_at
                      ? format(new Date(m.last_login_at), "MMM d, yyyy")
                      : m.invited_at
                        ? `Invited ${format(new Date(m.invited_at), "MMM d")}`
                        : "—"}
                  </TableCell>
                  {canManage ? (
                    <TableCell className="text-right">
                      {isSelf ? (
                        <span className="text-xs text-[var(--text-dim)]">—</span>
                      ) : (
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon-sm"
                              disabled={pendingId === m.id}
                              aria-label="Member actions"
                            >
                              <MoreHorizontal className="size-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="min-w-[180px]">
                            {m.role === "employee" ? (
                              <DropdownMenuItem onClick={() => patchMember(m.id, { role: "manager" })}>
                                <ArrowUpFromLine className="size-3.5" aria-hidden />
                                Promote to manager
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => patchMember(m.id, { role: "employee" })}>
                                <ArrowDownToLine className="size-3.5" aria-hidden />
                                Demote to employee
                              </DropdownMenuItem>
                            )}
                            {m.status === "active" ? (
                              <DropdownMenuItem onClick={() => patchMember(m.id, { status: "suspended" })}>
                                <Pause className="size-3.5" aria-hidden />
                                Suspend access
                              </DropdownMenuItem>
                            ) : (
                              <DropdownMenuItem onClick={() => patchMember(m.id, { status: "active" })}>
                                <Play className="size-3.5" aria-hidden />
                                Reactivate
                              </DropdownMenuItem>
                            )}
                            <DropdownMenuSeparator />
                            <DropdownMenuItem
                              variant="destructive"
                              onClick={() => removeMember(m.id)}
                            >
                              <Trash2 className="size-3.5" aria-hidden />
                              Remove
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      )}
                    </TableCell>
                  ) : null}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      {canManage ? (
        <InviteEmployeeDialog
          open={inviteOpen}
          onOpenChange={setInviteOpen}
          seatsRemaining={seatsRemaining}
          onInvited={(invited) => {
            toast.success(`Invite sent to ${invited.email}`, {
              description: `${invited.full_name} will appear here once they accept.`,
            });
            Promise.all([fetchTeam(), refresh()]);
          }}
        />
      ) : null}
    </div>
  );
}
