"use client";

import { useState } from "react";
import { Building2, Mail, User, Users } from "lucide-react";

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

interface CreateOrganizationDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (org: { client_id: string; manager_email: string; company_name: string }) => void;
}

interface FormState {
  company_name: string;
  manager_full_name: string;
  manager_email: string;
  seat_limit: string; // keep as string in the input, parse on submit
}

const INITIAL_STATE: FormState = {
  company_name: "",
  manager_full_name: "",
  manager_email: "",
  seat_limit: "5",
};

export function CreateOrganizationDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateOrganizationDialogProps) {
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
    if (!form.company_name.trim()) next.company_name = "Required";
    if (!form.manager_full_name.trim()) next.manager_full_name = "Required";
    if (!form.manager_email.trim()) {
      next.manager_email = "Required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.manager_email.trim())) {
      next.manager_email = "Invalid email";
    }
    const seat = Number.parseInt(form.seat_limit, 10);
    if (!Number.isFinite(seat) || seat < 1 || seat > 500) {
      next.seat_limit = "1–500";
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
      const res = await fetch("/api/admin/organizations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          company_name: form.company_name.trim(),
          manager_full_name: form.manager_full_name.trim(),
          manager_email: form.manager_email.trim().toLowerCase(),
          seat_limit: Number.parseInt(form.seat_limit, 10),
        }),
      });

      const payload = await res.json().catch(() => ({}));

      if (!res.ok) {
        setApiError(payload?.error ?? "Failed to create organization");
        setSubmitting(false);
        return;
      }

      onCreated({
        client_id: payload.client_id,
        manager_email: payload.manager_email,
        company_name: payload.company_name,
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

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex size-10 items-center justify-center rounded-[var(--radius-md)] bg-[color-mix(in_srgb,var(--brand-primary)_14%,transparent)] text-[var(--brand-primary)]">
              <Building2 className="size-5" />
            </div>
            <div>
              <DialogTitle>Create organization</DialogTitle>
              <DialogDescription>
                Provision a new client org and invite its first manager.
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5" noValidate>
          <Field label="Company name" required error={errors.company_name}>
            <Input
              type="text"
              placeholder="Acme Health Advisers"
              value={form.company_name}
              onChange={(e) => update("company_name", e.target.value)}
              disabled={submitting}
              autoFocus
              maxLength={200}
            />
          </Field>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <User className="size-3" aria-hidden />
                  Manager name
                </span>
              }
              required
              error={errors.manager_full_name}
            >
              <Input
                type="text"
                placeholder="Lindiwe Sithole"
                value={form.manager_full_name}
                onChange={(e) => update("manager_full_name", e.target.value)}
                disabled={submitting}
                maxLength={200}
              />
            </Field>

            <Field
              label={
                <span className="inline-flex items-center gap-1.5">
                  <Mail className="size-3" aria-hidden />
                  Manager email
                </span>
              }
              required
              error={errors.manager_email}
            >
              <Input
                type="email"
                placeholder="manager@acme.co.za"
                value={form.manager_email}
                onChange={(e) => update("manager_email", e.target.value)}
                disabled={submitting}
                maxLength={255}
              />
            </Field>
          </div>

          <Field
            label={
              <span className="inline-flex items-center gap-1.5">
                <Users className="size-3" aria-hidden />
                Seat limit
              </span>
            }
            hint="How many portal users this org can activate. Manager + employees. You can change this later."
            error={errors.seat_limit}
          >
            <Input
              type="number"
              min={1}
              max={500}
              value={form.seat_limit}
              onChange={(e) => update("seat_limit", e.target.value)}
              disabled={submitting}
              className="max-w-[160px]"
            />
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
            <Button type="submit" loading={submitting} disabled={submitting}>
              {submitting ? "Creating…" : "Create & send invite"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
