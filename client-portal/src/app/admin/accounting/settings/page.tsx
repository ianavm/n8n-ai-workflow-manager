"use client";

import { useEffect, useState } from "react";
import { createClient } from "@/lib/supabase/client";
import { Settings, Save, CheckCircle2 } from "lucide-react";

interface AcctConfig {
  id: string;
  client_id: string;
  company_legal_name: string | null;
  company_trading_name: string | null;
  company_vat_number: string | null;
  default_currency: string;
  vat_rate: number;
  invoice_prefix: string;
  default_payment_terms: string;
  auto_approve_bills_below: number;
  high_value_threshold: number;
  reminder_cadence_days: number[];
  escalation_after_days: number;
  accounting_software: string;
  payment_gateway: string;
  ocr_provider: string;
  comms_email: string;
  comms_chat: string;
  modules_enabled: Record<string, boolean>;
}

function formatCurrency(cents: number): string {
  return `R${(cents / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}`;
}

export default function SettingsPage() {
  const supabase = createClient();
  const [config, setConfig] = useState<AcctConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    async function load() {
      // Use config API which respects client selector session
      const stored = sessionStorage.getItem("acct_active_client_id");
      const params = stored ? `?client_id=${stored}` : "";
      const resp = await fetch(`/api/accounting/config${params}`);
      const result = await resp.json();
      if (result.data) setConfig(result.data as AcctConfig);
      setLoading(false);
    }
    load();
  }, []);

  async function handleSave() {
    if (!config) return;
    setSaving(true);
    await supabase.from("acct_config").update({
      company_legal_name: config.company_legal_name,
      company_trading_name: config.company_trading_name,
      company_vat_number: config.company_vat_number,
      default_currency: config.default_currency,
      vat_rate: config.vat_rate,
      invoice_prefix: config.invoice_prefix,
      default_payment_terms: config.default_payment_terms,
      auto_approve_bills_below: config.auto_approve_bills_below,
      high_value_threshold: config.high_value_threshold,
      escalation_after_days: config.escalation_after_days,
      accounting_software: config.accounting_software,
      payment_gateway: config.payment_gateway,
      ocr_provider: config.ocr_provider,
      comms_email: config.comms_email,
      comms_chat: config.comms_chat,
      modules_enabled: config.modules_enabled,
    }).eq("id", config.id);
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 3000);
  }

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold text-white">Finance Settings</h1>
        <div className="h-96 rounded-xl bg-[rgba(0,0,0,0.2)] animate-pulse" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="text-center py-12">
        <Settings className="mx-auto mb-4 text-gray-600" size={48} />
        <p className="text-gray-400">Accounting module not configured</p>
        <p className="text-xs text-gray-500 mt-1">Run setup_acct_supabase.py to initialize</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Finance Settings</h1>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-[#FF6D5A] text-white text-sm font-medium hover:bg-[#e85d4a] disabled:opacity-50"
        >
          {saved ? <CheckCircle2 size={16} /> : <Save size={16} />}
          {saving ? "Saving..." : saved ? "Saved!" : "Save Changes"}
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Company Details */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">Company Details</h2>
          <div className="space-y-3">
            <Field label="Legal Name" value={config.company_legal_name ?? ""} onChange={(v) => setConfig({ ...config, company_legal_name: v })} />
            <Field label="Trading Name" value={config.company_trading_name ?? ""} onChange={(v) => setConfig({ ...config, company_trading_name: v })} />
            <Field label="VAT Number" value={config.company_vat_number ?? ""} onChange={(v) => setConfig({ ...config, company_vat_number: v })} />
          </div>
        </div>

        {/* Tax & Invoice */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">Tax & Invoicing</h2>
          <div className="space-y-3">
            <SelectField label="Currency" value={config.default_currency} options={["ZAR", "USD", "EUR", "GBP"]} onChange={(v) => setConfig({ ...config, default_currency: v })} />
            <Field label="VAT Rate" value={String(config.vat_rate)} onChange={(v) => setConfig({ ...config, vat_rate: parseFloat(v) || 0.15 })} />
            <Field label="Invoice Prefix" value={config.invoice_prefix} onChange={(v) => setConfig({ ...config, invoice_prefix: v })} />
            <SelectField label="Payment Terms" value={config.default_payment_terms} options={["COD", "7 days", "14 days", "30 days", "60 days", "90 days"]} onChange={(v) => setConfig({ ...config, default_payment_terms: v })} />
          </div>
        </div>

        {/* Thresholds */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">Thresholds</h2>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-gray-400">Auto-Approve Bills Below</label>
              <p className="text-sm text-white mb-1">{formatCurrency(config.auto_approve_bills_below)}</p>
              <input type="range" min={0} max={10000000} step={100000} value={config.auto_approve_bills_below}
                onChange={(e) => setConfig({ ...config, auto_approve_bills_below: parseInt(e.target.value) })}
                className="w-full accent-[#FF6D5A]" />
            </div>
            <div>
              <label className="text-xs text-gray-400">High-Value Invoice Threshold</label>
              <p className="text-sm text-white mb-1">{formatCurrency(config.high_value_threshold)}</p>
              <input type="range" min={0} max={50000000} step={500000} value={config.high_value_threshold}
                onChange={(e) => setConfig({ ...config, high_value_threshold: parseInt(e.target.value) })}
                className="w-full accent-[#FF6D5A]" />
            </div>
            <Field label="Escalation After (days)" value={String(config.escalation_after_days)} onChange={(v) => setConfig({ ...config, escalation_after_days: parseInt(v) || 14 })} />
          </div>
        </div>

        {/* Integrations */}
        <div className="rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">Integrations</h2>
          <div className="space-y-3">
            <SelectField label="Accounting Software" value={config.accounting_software} options={["none", "quickbooks", "xero", "sage", "zoho", "dynamics"]} onChange={(v) => setConfig({ ...config, accounting_software: v })} />
            <SelectField label="Payment Gateway" value={config.payment_gateway} options={["none", "stripe", "payfast", "yoco", "peach", "paygate", "manual"]} onChange={(v) => setConfig({ ...config, payment_gateway: v })} />
            <SelectField label="OCR Provider" value={config.ocr_provider} options={["ai", "azure_doc_ai", "google_doc_ai", "dext", "hubdoc", "none"]} onChange={(v) => setConfig({ ...config, ocr_provider: v })} />
            <SelectField label="Email" value={config.comms_email} options={["gmail", "outlook", "none"]} onChange={(v) => setConfig({ ...config, comms_email: v })} />
            <SelectField label="Chat" value={config.comms_chat} options={["none", "whatsapp", "telegram", "slack", "teams"]} onChange={(v) => setConfig({ ...config, comms_chat: v })} />
          </div>
        </div>

        {/* Module Toggles */}
        <div className="lg:col-span-2 rounded-xl border border-[rgba(255,255,255,0.06)] bg-[rgba(0,0,0,0.2)] p-5 space-y-4">
          <h2 className="text-sm font-semibold text-white">Modules</h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(config.modules_enabled).map(([key, enabled]) => (
              <label key={key} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(e) => setConfig({
                    ...config,
                    modules_enabled: { ...config.modules_enabled, [key]: e.target.checked },
                  })}
                  className="rounded accent-[#FF6D5A]"
                />
                <span className="text-sm text-gray-300 capitalize">{key.replace(/_/g, " ")}</span>
              </label>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function Field({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-gray-400">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 px-3 py-2 rounded-lg bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.06)] text-white text-sm focus:outline-none focus:border-[rgba(255,109,90,0.3)]"
      />
    </div>
  );
}

function SelectField({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="text-xs text-gray-400">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full mt-1 px-3 py-2 rounded-lg bg-[rgba(0,0,0,0.3)] border border-[rgba(255,255,255,0.06)] text-white text-sm appearance-none focus:outline-none"
      >
        {options.map((opt) => (
          <option key={opt} value={opt} className="bg-gray-900">{opt}</option>
        ))}
      </select>
    </div>
  );
}
