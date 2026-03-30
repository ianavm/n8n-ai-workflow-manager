"use client";

import { useEffect, useState, useCallback } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  User,
  Shield,
  AlertTriangle,
  CheckCircle,
  Save,
  Users,
} from "lucide-react";

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

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "10px 14px",
  borderRadius: "8px",
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.1)",
  color: "#fff",
  fontSize: "14px",
  outline: "none",
  fontFamily: "inherit",
};

const labelStyle: React.CSSProperties = {
  fontSize: "12px",
  fontWeight: 600,
  color: "#6B7280",
  textTransform: "uppercase" as const,
  letterSpacing: "0.5px",
  marginBottom: "6px",
  display: "block",
};

function ficaBadge(status: string | null) {
  if (!status) return { color: "#6B7280", bg: "rgba(107,114,128,0.1)", label: "Unknown" };
  const s = status.toLowerCase();
  if (s === "verified" || s === "complete")
    return { color: "#10B981", bg: "rgba(16,185,129,0.1)", label: "FICA Verified" };
  if (s === "pending")
    return { color: "#F59E0B", bg: "rgba(245,158,11,0.1)", label: "FICA Pending" };
  return { color: "#EF4444", bg: "rgba(239,68,68,0.1)", label: "FICA Incomplete" };
}

function riskColor(risk: string | null): string {
  if (!risk) return "#6B7280";
  const r = risk.toLowerCase();
  if (r === "conservative") return "#10B981";
  if (r === "moderate") return "#F59E0B";
  if (r === "aggressive") return "#EF4444";
  return "#6C63FF";
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
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchProfile = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: faClient, error: clientErr } = await supabase
      .from("fa_clients")
      .select("*")
      .eq("portal_client_id", userData.user.id)
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
      physical_address: faClient.physical_address || "",
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
      setSaveMsg("Failed to save changes.");
    } else {
      setSaveMsg("Profile updated successfully.");
      setTimeout(() => setSaveMsg(null), 3000);
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #6C63FF",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  if (!client) return null;

  const fica = ficaBadge(client.fica_status);

  return (
    <div>
      <div style={{ marginBottom: "24px" }}>
        <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>My Profile</h1>
        <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
          Your personal and financial information.
        </p>
      </div>

      {/* Personal Info (read-only fields) */}
      <div style={{ ...glassCard, marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
          <User size={18} style={{ color: "#6C63FF" }} />
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff" }}>Personal Information</h3>
          <div
            style={{
              marginLeft: "auto",
              display: "inline-flex",
              alignItems: "center",
              gap: "6px",
              padding: "4px 12px",
              borderRadius: "20px",
              background: fica.bg,
              color: fica.color,
              fontSize: "12px",
              fontWeight: 600,
            }}
          >
            {fica.color === "#10B981" ? <CheckCircle size={12} /> : <AlertTriangle size={12} />}
            {fica.label}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
          <div>
            <label style={labelStyle}>First Name</label>
            <div style={{ color: "#fff", fontSize: "14px" }}>{client.first_name}</div>
          </div>
          <div>
            <label style={labelStyle}>Last Name</label>
            <div style={{ color: "#fff", fontSize: "14px" }}>{client.last_name}</div>
          </div>
          <div>
            <label style={labelStyle}>Email</label>
            <div style={{ color: "#fff", fontSize: "14px" }}>{client.email}</div>
          </div>
          <div>
            <label style={labelStyle}>ID Number</label>
            <div style={{ color: "#fff", fontSize: "14px" }}>{client.id_number || "---"}</div>
          </div>
          <div>
            <label style={labelStyle}>Date of Birth</label>
            <div style={{ color: "#fff", fontSize: "14px" }}>
              {client.date_of_birth
                ? new Date(client.date_of_birth).toLocaleDateString("en-ZA")
                : "---"}
            </div>
          </div>
          <div>
            <label style={labelStyle}>Risk Tolerance</label>
            <div style={{ color: riskColor(client.risk_tolerance), fontSize: "14px", fontWeight: 600 }}>
              {client.risk_tolerance || "Not assessed"}
            </div>
          </div>
        </div>
      </div>

      {/* Editable Fields */}
      <div style={{ ...glassCard, marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
          <Shield size={18} style={{ color: "#00D4AA" }} />
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff" }}>Contact & Employment</h3>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginBottom: "20px" }}>
          <div>
            <label style={labelStyle}>Phone</label>
            <input
              type="tel"
              style={inputStyle}
              value={editable.phone}
              onChange={(e) => setEditable({ ...editable, phone: e.target.value })}
            />
          </div>
          <div>
            <label style={labelStyle}>Mobile</label>
            <input
              type="tel"
              style={inputStyle}
              value={editable.mobile}
              onChange={(e) => setEditable({ ...editable, mobile: e.target.value })}
            />
          </div>
          <div style={{ gridColumn: "1 / -1" }}>
            <label style={labelStyle}>Physical Address</label>
            <input
              type="text"
              style={inputStyle}
              value={editable.physical_address}
              onChange={(e) => setEditable({ ...editable, physical_address: e.target.value })}
            />
          </div>
          <div>
            <label style={labelStyle}>Employer</label>
            <input
              type="text"
              style={inputStyle}
              value={editable.employer}
              onChange={(e) => setEditable({ ...editable, employer: e.target.value })}
            />
          </div>
          <div>
            <label style={labelStyle}>Occupation</label>
            <input
              type="text"
              style={inputStyle}
              value={editable.occupation}
              onChange={(e) => setEditable({ ...editable, occupation: e.target.value })}
            />
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 20px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #6C63FF, #5B5FC7)",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 600,
              border: "none",
              cursor: saving ? "not-allowed" : "pointer",
              opacity: saving ? 0.6 : 1,
              fontFamily: "inherit",
            }}
          >
            <Save size={16} />
            {saving ? "Saving..." : "Save Changes"}
          </button>
          {saveMsg && (
            <span style={{ fontSize: "13px", color: saveMsg.includes("Failed") ? "#EF4444" : "#10B981" }}>
              {saveMsg}
            </span>
          )}
        </div>
      </div>

      {/* Dependents */}
      <div style={{ ...glassCard, marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "20px" }}>
          <Users size={18} style={{ color: "#F59E0B" }} />
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff" }}>Dependents</h3>
        </div>

        {dependents.length === 0 ? (
          <p style={{ fontSize: "13px", color: "#6B7280" }}>No dependents on record.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {dependents.map((d) => (
              <div
                key={d.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px",
                  borderRadius: "10px",
                  background: "rgba(255,255,255,0.03)",
                  border: "1px solid rgba(255,255,255,0.04)",
                }}
              >
                <div>
                  <div style={{ fontSize: "14px", fontWeight: 500, color: "#fff" }}>
                    {d.first_name} {d.last_name}
                  </div>
                  <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "2px" }}>
                    {d.relationship}
                    {d.date_of_birth && ` - Born ${new Date(d.date_of_birth).toLocaleDateString("en-ZA")}`}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Financial Summary (read-only) */}
      {client.financial_summary && Object.keys(client.financial_summary).length > 0 && (
        <div style={glassCard}>
          <h3 style={{ fontSize: "16px", fontWeight: 600, color: "#fff", marginBottom: "16px" }}>
            Financial Summary
          </h3>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
            {Object.entries(client.financial_summary).map(([key, val]) => (
              <div key={key}>
                <label style={labelStyle}>{key.replace(/_/g, " ")}</label>
                <div style={{ color: "#fff", fontSize: "14px" }}>{String(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
