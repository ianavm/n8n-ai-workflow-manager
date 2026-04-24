"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle,
  Save,
  Shield,
  User,
  Users,
} from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Badge } from "@/components/ui-shadcn/badge";
import { Button } from "@/components/ui-shadcn/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui-shadcn/card";
import { Field } from "@/components/ui-shadcn/field";
import { Input } from "@/components/ui-shadcn/input";

interface FaClient {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  mobile: string | null;
  physical_address: string | null;
  employer: string | null;
  occupation: string | null;
  id_number: string | null;
  date_of_birth: string | null;
  risk_tolerance: string | null;
  fica_status: string | null;
  financial_summary: Record<string, unknown> | null;
}

interface FaDependent {
  id: string;
  first_name: string;
  last_name: string;
  relationship: string;
  date_of_birth: string | null;
}

interface EditableFields {
  phone: string;
  mobile: string;
  physical_address: string;
  employer: string;
  occupation: string;
}

function ficaBadge(status: string | null) {
  if (!status) return { tone: "neutral" as const, label: "Unknown", verified: false };
  const s = status.toLowerCase();
  if (s === "verified" || s === "complete")
    return { tone: "success" as const, label: "FICA Verified", verified: true };
  if (s === "pending") return { tone: "warning" as const, label: "FICA Pending", verified: false };
  return { tone: "danger" as const, label: "FICA Incomplete", verified: false };
}

function riskColor(risk: string | null): string {
  if (!risk) return "var(--text-dim)";
  const r = risk.toLowerCase();
  if (r === "conservative") return "var(--accent-teal)";
  if (r === "moderate") return "var(--warning)";
  if (r === "aggressive") return "var(--danger)";
  return "var(--accent-purple)";
}

export default function AdvisoryProfile() {
  const supabase = createClient();
  const [client, setClient] = useState<FaClient | null>(null);
  const [dependents, setDependents] = useState<FaDependent[]>([]);
  const [editable, setEditable] = useState<EditableFields>({
    phone: "",
    mobile: "",
    physical_address: "",
    employer: "",
    occupation: "",
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: portalClient } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", userData.user.id)
      .single();
    if (!portalClient) {
      setError("No portal account found");
      setLoading(false);
      return;
    }

    const { data: faClient, error: clientErr } = await supabase
      .from("fa_clients")
      .select("*")
      .eq("portal_client_id", portalClient.id)
      .single();

    if (clientErr || !faClient) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    setClient(faClient);
    setEditable({
      phone: faClient.phone || "",
      mobile: faClient.mobile || "",
      physical_address:
        typeof faClient.physical_address === "object" && faClient.physical_address !== null
          ? JSON.stringify(faClient.physical_address)
          : faClient.physical_address || "",
      employer: faClient.employer || "",
      occupation: faClient.occupation || "",
    });

    const { data: deps } = await supabase
      .from("fa_dependents")
      .select("id, first_name, last_name, relationship, date_of_birth")
      .eq("client_id", faClient.id)
      .order("created_at", { ascending: true });

    setDependents(deps || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchProfile();
  }, [fetchProfile]);

  async function handleSave() {
    if (!client) return;
    setSaving(true);
    setSaveMsg(null);

    const { error: updateErr } = await supabase
      .from("fa_clients")
      .update({
        phone: editable.phone || null,
        mobile: editable.mobile || null,
        physical_address: editable.physical_address || null,
        employer: editable.employer || null,
        occupation: editable.occupation || null,
      })
      .eq("id", client.id);

    setSaving(false);
    if (updateErr) {
      setSaveMsg({ type: "error", text: "Failed to save changes." });
    } else {
      setSaveMsg({ type: "success", text: "Profile updated successfully." });
      setTimeout(() => setSaveMsg(null), 3000);
    }
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Your profile" description="Personal and financial information." />
        <LoadingState variant="card" rows={5} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Your profile" description="Personal and financial information." />
        <ErrorState title="Profile unavailable" description={error} onRetry={fetchProfile} />
      </div>
    );
  }

  if (!client) return null;

  const fica = ficaBadge(client.fica_status);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Advisory"
        title="Your profile"
        description="Personal and financial information on file with your adviser."
      />

      {/* Personal Information */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-teal)_12%,transparent)] text-[var(--accent-teal)]">
                <User className="size-4" aria-hidden />
              </span>
              <CardTitle className="text-base">Personal information</CardTitle>
            </div>
            <Badge tone={fica.tone} appearance="soft" size="md">
              {fica.verified ? <CheckCircle className="size-3" /> : <AlertTriangle className="size-3" />}
              {fica.label}
            </Badge>
          </div>
        </CardHeader>
        <CardContent className="pt-6">
          <dl className="grid gap-4 md:grid-cols-2">
            <ReadOnlyRow label="First name" value={client.first_name} />
            <ReadOnlyRow label="Last name" value={client.last_name} />
            <ReadOnlyRow label="Email" value={client.email} />
            <ReadOnlyRow label="ID number" value={client.id_number || "—"} />
            <ReadOnlyRow
              label="Date of birth"
              value={
                client.date_of_birth
                  ? new Date(client.date_of_birth).toLocaleDateString("en-ZA")
                  : "—"
              }
            />
            <ReadOnlyRow
              label="Risk tolerance"
              value={
                <span style={{ color: riskColor(client.risk_tolerance), fontWeight: 600 }}>
                  {client.risk_tolerance || "Not assessed"}
                </span>
              }
            />
          </dl>
        </CardContent>
      </Card>

      {/* Contact & Employment (editable) */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--accent-purple)_12%,transparent)] text-[var(--accent-purple)]">
              <Shield className="size-4" aria-hidden />
            </span>
            <CardTitle className="text-base">Contact & employment</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-6 flex flex-col gap-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Phone">
              <Input
                type="tel"
                value={editable.phone}
                onChange={(e) => setEditable({ ...editable, phone: e.target.value })}
              />
            </Field>
            <Field label="Mobile">
              <Input
                type="tel"
                value={editable.mobile}
                onChange={(e) => setEditable({ ...editable, mobile: e.target.value })}
              />
            </Field>
            <div className="md:col-span-2">
              <Field label="Physical address">
                <Input
                  type="text"
                  value={editable.physical_address}
                  onChange={(e) => setEditable({ ...editable, physical_address: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Employer">
              <Input
                type="text"
                value={editable.employer}
                onChange={(e) => setEditable({ ...editable, employer: e.target.value })}
              />
            </Field>
            <Field label="Occupation">
              <Input
                type="text"
                value={editable.occupation}
                onChange={(e) => setEditable({ ...editable, occupation: e.target.value })}
              />
            </Field>
          </div>

          <div className="flex items-center gap-3">
            <Button variant="default" onClick={handleSave} loading={saving}>
              <Save className="size-4" />
              Save changes
            </Button>
            {saveMsg ? (
              <span
                className="text-sm font-medium"
                style={{ color: saveMsg.type === "success" ? "var(--accent-teal)" : "var(--danger)" }}
              >
                {saveMsg.text}
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      {/* Dependents */}
      <Card variant="default" padding="lg">
        <CardHeader>
          <div className="flex items-center gap-2">
            <span className="grid place-items-center size-8 rounded-[var(--radius-sm)] bg-[color-mix(in_srgb,var(--warning)_12%,transparent)] text-[var(--warning)]">
              <Users className="size-4" aria-hidden />
            </span>
            <CardTitle className="text-base">Dependents</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {dependents.length === 0 ? (
            <EmptyState inline title="No dependents on record" />
          ) : (
            <ul className="flex flex-col gap-2">
              {dependents.map((d) => (
                <li
                  key={d.id}
                  className="flex items-center justify-between gap-3 p-3 rounded-[var(--radius-sm)] border border-[var(--border-subtle)] bg-[var(--bg-card)]"
                >
                  <div>
                    <p className="text-sm font-medium text-foreground">
                      {d.first_name} {d.last_name}
                    </p>
                    <p className="text-xs text-[var(--text-dim)] mt-0.5 capitalize">
                      {d.relationship}
                      {d.date_of_birth ? ` · Born ${new Date(d.date_of_birth).toLocaleDateString("en-ZA")}` : ""}
                    </p>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Financial summary */}
      {client.financial_summary && Object.keys(client.financial_summary).length > 0 ? (
        <Card variant="default" padding="lg">
          <CardHeader>
            <CardTitle className="text-base">Financial summary</CardTitle>
          </CardHeader>
          <CardContent className="pt-4">
            <dl className="grid gap-3 md:grid-cols-2">
              {Object.entries(client.financial_summary).map(([key, val]) => (
                <ReadOnlyRow key={key} label={key.replace(/_/g, " ")} value={String(val)} />
              ))}
            </dl>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function ReadOnlyRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-[11px] font-semibold uppercase tracking-[0.1em] text-[var(--text-dim)] mb-1">
        {label}
      </dt>
      <dd className="text-sm text-foreground">{value}</dd>
    </div>
  );
}
