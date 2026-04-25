"use client";

import { useEffect, useState } from "react";
import { Users } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui-shadcn/dialog";
import { Button } from "@/components/ui-shadcn/button";
import { Input } from "@/components/ui-shadcn/input";
import { Field } from "@/components/ui-shadcn/field";
import { Alert, AlertDescription } from "@/components/ui-shadcn/alert";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  org: {
    id: string;
    company_name: string | null;
    seat_limit: number;
    seats_used: number;
  } | null;
  onUpdated: (newLimit: number) => void;
}

export function AdjustSeatsDialog({ open, onOpenChange, org, onUpdated }: Props) {
  const [value, setValue] = useState<string>("5");
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Reset value whenever the dialog opens with a new org.
  useEffect(() => {
    if (open && org) {
      setValue(String(org.seat_limit));
      setApiError(null);
    }
  }, [open, org]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!org) return;
    const seatLimit = Number.parseInt(value, 10);
    if (!Number.isFinite(seatLimit) || seatLimit < 1 || seatLimit > 500) {
      setApiError("Seat limit must be between 1 and 500");
      return;
    }
    if (seatLimit === org.seat_limit) {
      onOpenChange(false);
      return;
    }

    setSubmitting(true);
    setApiError(null);
    try {
      const res = await fetch(`/api/admin/organizations/${org.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seat_limit: seatLimit }),
      });
      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        setApiError(payload?.error ?? "Failed to update");
        setSubmitting(false);
        return;
      }
      onUpdated(seatLimit);
      onOpenChange(false);
    } catch {
      setApiError("Network error. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  if (!org) return null;

  const newLimit = Number.parseInt(value, 10) || 0;
  const wouldShrinkBelowUsage = newLimit < org.seats_used;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[460px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--brand-primary)_14%,transparent)] text-[var(--brand-primary)]">
              <Users className="size-5" />
            </div>
            <div>
              <DialogTitle>Adjust seat limit</DialogTitle>
              <DialogDescription>
                {org.company_name ?? "Organization"} · currently {org.seats_used} of {org.seat_limit} seats used
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          <Field
            label="New seat limit"
            hint="Manager + employees combined. Cannot drop below current usage."
            error={wouldShrinkBelowUsage ? `At least ${org.seats_used} required to cover active members` : undefined}
          >
            <Input
              type="number"
              min={1}
              max={500}
              value={value}
              onChange={(e) => setValue(e.target.value)}
              disabled={submitting}
              autoFocus
              className="max-w-[160px]"
            />
          </Field>

          {apiError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiError}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter className="mt-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              loading={submitting}
              disabled={submitting || wouldShrinkBelowUsage || newLimit < 1}
            >
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
