"use client";

import { useState } from "react";
import { Mail, User, UserPlus } from "lucide-react";

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui-shadcn/select";

interface Props {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onInvited: (member: { email: string; full_name: string; role: "manager" | "employee" }) => void;
  seatsRemaining: number;
}

interface FormState {
  full_name: string;
  email: string;
  role: "manager" | "employee";
}

const INITIAL_STATE: FormState = {
  full_name: "",
  email: "",
  role: "employee",
};

export function InviteEmployeeDialog({ open, onOpenChange, onInvited, seatsRemaining }: Props) {
  const [form, setForm] = useState<FormState>(INITIAL_STATE);
  const [errors, setErrors] = useState<Partial<Record<keyof FormState, string>>>({});
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  function reset() {
    setForm(INITIAL_STATE);
    setErrors({});
    setApiError(null);
    setSubmitting(false);
  }

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (errors[key]) setErrors((prev) => ({ ...prev, [key]: undefined }));
  }

  function validate(): boolean {
    const next: Partial<Record<keyof FormState, string>> = {};
    if (!form.full_name.trim()) next.full_name = "Required";
    if (!form.email.trim()) {
      next.email = "Required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
      next.email = "Invalid email";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setApiError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const res = await fetch("/api/portal/team/invite", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: form.email.trim().toLowerCase(),
          full_name: form.full_name.trim(),
          role: form.role,
        }),
      });

      const payload = await res.json().catch(() => ({}));
      if (!res.ok) {
        setApiError(payload?.error ?? "Failed to send invite");
        setSubmitting(false);
        return;
      }

      onInvited({
        email: form.email.trim().toLowerCase(),
        full_name: form.full_name.trim(),
        role: form.role,
      });
      reset();
      onOpenChange(false);
    } catch {
      setApiError("Network error. Please try again.");
      setSubmitting(false);
    }
  }

  function handleOpenChange(next: boolean) {
    if (!next && !submitting) reset();
    onOpenChange(next);
  }

  const seatsExhausted = seatsRemaining <= 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--brand-primary)_14%,transparent)] text-[var(--brand-primary)]">
              <UserPlus className="size-5" />
            </div>
            <div>
              <DialogTitle>Invite team member</DialogTitle>
              <DialogDescription>
                {seatsExhausted
                  ? "Your seat limit is full. Contact AnyVision to add more seats."
                  : `${seatsRemaining} ${seatsRemaining === 1 ? "seat" : "seats"} remaining.`}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <User className="size-3" aria-hidden />
                  Full name
                </span>
              }
              required
              error={errors.full_name}
            >
              <Input
                type="text"
                placeholder="Jane Doe"
                value={form.full_name}
                onChange={(e) => update("full_name", e.target.value)}
                disabled={submitting || seatsExhausted}
                autoFocus
                maxLength={200}
              />
            </Field>

            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="size-3" aria-hidden />
                  Work email
                </span>
              }
              required
              error={errors.email}
            >
              <Input
                type="email"
                placeholder="jane@company.com"
                value={form.email}
                onChange={(e) => update("email", e.target.value)}
                disabled={submitting || seatsExhausted}
                maxLength={255}
              />
            </Field>
          </div>

          <Field
            label="Role"
            hint="Managers can invite/manage other members. Employees see read-only team."
          >
            <Select
              value={form.role}
              onValueChange={(v) => update("role", v as "manager" | "employee")}
              disabled={submitting || seatsExhausted}
            >
              <SelectTrigger className="w-full sm:w-[240px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="employee">Employee</SelectItem>
                <SelectItem value="manager">Manager</SelectItem>
              </SelectContent>
            </Select>
          </Field>

          {apiError ? (
            <Alert variant="destructive">
              <AlertDescription>{apiError}</AlertDescription>
            </Alert>
          ) : null}

          <DialogFooter className="mt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => handleOpenChange(false)}
              disabled={submitting}
            >
              Cancel
            </Button>
            <Button type="submit" loading={submitting} disabled={submitting || seatsExhausted}>
              {submitting ? "Sending invite…" : "Send invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
