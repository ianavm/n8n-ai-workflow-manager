"use client";

import { useEffect, useState, useCallback } from "react";
import { Building2, Users, Calendar, Shield, Plus, X } from "lucide-react";

interface OfficeSummary {
  firm_id: string;
  firm_name: string;
  total_advisers: number;
  total_clients: number;
  active_clients: number;
  meetings_this_month: number;
  compliance_score: number;
}

interface CreateOfficeForm {
  firm_name: string;
  fsp_number: string;
  contact_email: string;
}

export default function OfficesPage() {
  const [offices, setOffices] = useState<OfficeSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<CreateOfficeForm>({
    firm_name: "",
    fsp_number: "",
    contact_email: "",
  });
  const [formError, setFormError] = useState<string | null>(null);

  const fetchOffices = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetch("/api/advisory/offices");
    if (res.ok) {
      const json = await res.json();
      setOffices(json.data ?? []);
    } else if (res.status === 403) {
      setError("Access denied. Super admin role required.");
    } else {
      setError("Failed to load offices.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchOffices();
  }, [fetchOffices]);

  const handleCreate = async () => {
    setFormError(null);
    if (!form.firm_name.trim()) {
      setFormError("Firm name is required.");
      return;
    }
    if (!form.contact_email.trim()) {
      setFormError("Contact email is required.");
      return;
    }

    setCreating(true);
    const res = await fetch("/api/advisory/offices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        firm_name: form.firm_name.trim(),
        fsp_number: form.fsp_number.trim() || undefined,
        contact_email: form.contact_email.trim(),
      }),
    });

    if (res.ok) {
      setShowModal(false);
      setForm({ firm_name: "", fsp_number: "", contact_email: "" });
      fetchOffices();
    } else {
      const json = await res.json();
      setFormError(json.error ?? "Failed to create office.");
    }
    setCreating(false);
  };

  const updateForm = (field: keyof CreateOfficeForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const complianceColor = (score: number): string => {
    if (score >= 90) return "#10B981";
    if (score >= 70) return "#F59E0B";
    if (score >= 50) return "#F97316";
    return "#EF4444";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin w-8 h-8 border-2 border-[#00A651] border-t-transparent rounded-full" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-card p-12 text-center">
        <Shield size={32} className="text-[#EF4444] mx-auto mb-3 opacity-70" />
        <p className="text-sm text-[#EF4444]">{error}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div className="relative">
          <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
          <div className="relative">
            <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
              Office <span className="gradient-text">Management</span>
            </h1>
            <p className="text-sm text-[var(--text-muted)] mt-2">
              {offices.length} {offices.length === 1 ? "office" : "offices"}{" "}
              across all firms
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#00A651] hover:bg-[#5A52E0] text-white rounded-lg text-sm font-medium transition-colors"
        >
          <Plus size={16} />
          Add Office
        </button>
      </div>

      {/* Office Grid */}
      {offices.length === 0 ? (
        <div className="glass-card p-12 text-center">
          <Building2
            size={32}
            className="text-[var(--text-dim)] mx-auto mb-3 opacity-50"
          />
          <p className="text-sm text-[var(--text-dim)]">
            No offices configured yet. Add your first office to get started.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {offices.map((office) => (
            <div
              key={office.firm_id}
              className="glass-card p-5 hover:border-[rgba(108,99,255,0.3)] border border-transparent transition-all cursor-pointer group"
            >
              {/* Office Name */}
              <div className="flex items-center gap-3 mb-4">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                  style={{
                    background: "linear-gradient(135deg, #00A651, #00D4AA)",
                  }}
                >
                  <Building2 size={20} className="text-white" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-white font-semibold text-sm truncate group-hover:text-[#00A651] transition-colors">
                    {office.firm_name}
                  </h3>
                  <p className="text-xs text-[var(--text-dim)]">
                    {office.active_clients} active of {office.total_clients}{" "}
                    clients
                  </p>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-[rgba(255,255,255,0.03)] rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Users size={12} className="text-[#00A651]" />
                    <span className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">
                      Advisers
                    </span>
                  </div>
                  <p className="text-lg font-bold text-white">
                    {office.total_advisers}
                  </p>
                </div>

                <div className="bg-[rgba(255,255,255,0.03)] rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Calendar size={12} className="text-[#00D4AA]" />
                    <span className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">
                      Meetings
                    </span>
                  </div>
                  <p className="text-lg font-bold text-white">
                    {office.meetings_this_month}
                  </p>
                </div>

                <div className="bg-[rgba(255,255,255,0.03)] rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Users size={12} className="text-[#F59E0B]" />
                    <span className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">
                      Clients
                    </span>
                  </div>
                  <p className="text-lg font-bold text-white">
                    {office.total_clients}
                  </p>
                </div>

                <div className="bg-[rgba(255,255,255,0.03)] rounded-lg p-3">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Shield
                      size={12}
                      style={{ color: complianceColor(office.compliance_score) }}
                    />
                    <span className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">
                      Compliance
                    </span>
                  </div>
                  <p
                    className="text-lg font-bold"
                    style={{ color: complianceColor(office.compliance_score) }}
                  >
                    {office.compliance_score}%
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Office Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass-card w-full max-w-md mx-4 p-6 space-y-5">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">
                Add New Office
              </h2>
              <button
                onClick={() => {
                  setShowModal(false);
                  setFormError(null);
                }}
                className="text-[var(--text-dim)] hover:text-white transition-colors"
              >
                <X size={20} />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs text-[var(--text-muted)] mb-1.5">
                  Firm Name *
                </label>
                <input
                  type="text"
                  value={form.firm_name}
                  onChange={(e) => updateForm("firm_name", e.target.value)}
                  placeholder="e.g. Wealth Partners Cape Town"
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-[var(--text-muted)] mb-1.5">
                  FSP Number
                </label>
                <input
                  type="text"
                  value={form.fsp_number}
                  onChange={(e) => updateForm("fsp_number", e.target.value)}
                  placeholder="e.g. 12345"
                  className="w-full"
                />
              </div>

              <div>
                <label className="block text-xs text-[var(--text-muted)] mb-1.5">
                  Contact Email *
                </label>
                <input
                  type="email"
                  value={form.contact_email}
                  onChange={(e) => updateForm("contact_email", e.target.value)}
                  placeholder="e.g. office@wealthpartners.co.za"
                  className="w-full"
                />
              </div>
            </div>

            {formError && (
              <p className="text-xs text-[#EF4444]">{formError}</p>
            )}

            <div className="flex items-center justify-end gap-3 pt-2">
              <button
                onClick={() => {
                  setShowModal(false);
                  setFormError(null);
                }}
                className="px-4 py-2 text-sm text-[var(--text-muted)] hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating}
                className="flex items-center gap-2 px-4 py-2 bg-[#00A651] hover:bg-[#5A52E0] disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-colors"
              >
                {creating ? (
                  <div className="animate-spin w-4 h-4 border-2 border-white border-t-transparent rounded-full" />
                ) : (
                  <Plus size={16} />
                )}
                Create Office
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
