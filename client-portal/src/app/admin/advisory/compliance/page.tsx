"use client";

import { useEffect, useState } from "react";
import {
  ShieldCheck,
  AlertTriangle,
  FileWarning,
  UserX,
  Clock,
  ShieldAlert,
} from "lucide-react";

interface ComplianceData {
  missing_popia_consent: number;
  missing_fais_disclosure: number;
  expired_consent: number;
  overdue_tasks: number;
  fica_verification_gaps: number;
  total_clients: number;
  compliant_clients: number;
  clients_needing_attention: ComplianceClient[];
}

interface ComplianceClient {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  issues: string[];
}

interface ComplianceCard {
  label: string;
  value: number;
  icon: React.ElementType;
  color: string;
  bgColor: string;
}

export default function CompliancePage() {
  const [data, setData] = useState<ComplianceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function fetchCompliance() {
      const res = await fetch("/api/advisory/compliance");
      if (res.ok) {
        const json = await res.json();
        setData(json.data);
      } else {
        const json = await res.json();
        setError(json.error ?? "Failed to load compliance data");
      }
      setLoading(false);
    }
    fetchCompliance();
  }, []);

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
        <ShieldAlert
          size={32}
          className="text-red-400 mx-auto mb-3 opacity-50"
        />
        <p className="text-sm text-red-400">{error}</p>
      </div>
    );
  }

  if (!data) return null;

  const complianceRate =
    data.total_clients > 0
      ? Math.round((data.compliant_clients / data.total_clients) * 100)
      : 0;

  const cards: ComplianceCard[] = [
    {
      label: "Missing POPIA Consent",
      value: data.missing_popia_consent,
      icon: FileWarning,
      color: "#EF4444",
      bgColor: "rgba(239, 68, 68, 0.1)",
    },
    {
      label: "Missing FAIS Disclosure",
      value: data.missing_fais_disclosure,
      icon: ShieldAlert,
      color: "#F97316",
      bgColor: "rgba(249, 115, 22, 0.1)",
    },
    {
      label: "Expired Consent",
      value: data.expired_consent,
      icon: Clock,
      color: "#F59E0B",
      bgColor: "rgba(245, 158, 11, 0.1)",
    },
    {
      label: "Overdue Tasks",
      value: data.overdue_tasks,
      icon: AlertTriangle,
      color: "#EF4444",
      bgColor: "rgba(239, 68, 68, 0.1)",
    },
    {
      label: "FICA Verification Gaps",
      value: data.fica_verification_gaps,
      icon: UserX,
      color: "#F97316",
      bgColor: "rgba(249, 115, 22, 0.1)",
    },
  ];

  const totalIssues = cards.reduce((sum, c) => sum + c.value, 0);

  return (
    <div className="space-y-6 max-w-[1200px]">
      {/* Header */}
      <div className="relative">
        <div className="absolute -top-4 -left-4 w-32 h-32 rounded-full bg-[rgba(108,99,255,0.12)] blur-3xl pointer-events-none" />
        <div className="relative">
          <h1 className="text-3xl lg:text-4xl font-bold text-white tracking-tight">
            <span className="gradient-text">Compliance</span> Dashboard
          </h1>
          <p className="text-sm text-[#B0B8C8] mt-2">
            Regulatory compliance overview for your firm
          </p>
        </div>
      </div>

      {/* Overall Score */}
      <div className="glass-card p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold text-white mb-1">
              Overall Compliance Rate
            </h2>
            <p className="text-sm text-[#6B7280]">
              {data.compliant_clients} of {data.total_clients} clients fully
              compliant
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div
              className="w-16 h-16 rounded-full flex items-center justify-center border-4"
              style={{
                borderColor:
                  complianceRate >= 90
                    ? "#10B981"
                    : complianceRate >= 70
                      ? "#F59E0B"
                      : "#EF4444",
              }}
            >
              <span
                className="text-xl font-bold"
                style={{
                  color:
                    complianceRate >= 90
                      ? "#10B981"
                      : complianceRate >= 70
                        ? "#F59E0B"
                        : "#EF4444",
                }}
              >
                {complianceRate}%
              </span>
            </div>
            <ShieldCheck
              size={24}
              className={
                totalIssues === 0 ? "text-emerald-400" : "text-amber-400"
              }
            />
          </div>
        </div>
      </div>

      {/* Issue Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="glass-card p-4">
              <div className="flex items-center gap-3 mb-3">
                <div
                  className="w-10 h-10 rounded-lg flex items-center justify-center"
                  style={{ backgroundColor: card.bgColor }}
                >
                  <Icon size={18} style={{ color: card.color }} />
                </div>
              </div>
              <div
                className="text-2xl font-bold mb-1"
                style={{
                  color: card.value > 0 ? card.color : "#10B981",
                }}
              >
                {card.value}
              </div>
              <div className="text-xs text-[#6B7280]">{card.label}</div>
            </div>
          );
        })}
      </div>

      {/* Clients Needing Attention */}
      {data.clients_needing_attention &&
        data.clients_needing_attention.length > 0 && (
          <div className="glass-card overflow-hidden">
            <div className="px-4 py-3 border-b border-[rgba(255,255,255,0.06)]">
              <h3 className="text-sm font-semibold text-white">
                Clients Needing Attention
              </h3>
            </div>
            <table className="w-full">
              <thead>
                <tr className="border-b border-[rgba(255,255,255,0.06)]">
                  <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                    Client
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                    Email
                  </th>
                  <th className="text-left px-4 py-3 text-xs font-medium text-[#6B7280] uppercase tracking-wider">
                    Issues
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.clients_needing_attention.map((c) => (
                  <tr
                    key={c.id}
                    className="border-b border-[rgba(255,255,255,0.04)] hover:bg-[rgba(255,255,255,0.02)] transition-colors"
                  >
                    <td className="px-4 py-3 text-sm font-medium text-white">
                      {c.first_name} {c.last_name}
                    </td>
                    <td className="px-4 py-3 text-sm text-[#B0B8C8]">
                      {c.email}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {c.issues.map((issue) => (
                          <span
                            key={issue}
                            className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-red-500/10 text-red-400 border border-red-500/20"
                          >
                            {issue}
                          </span>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}
