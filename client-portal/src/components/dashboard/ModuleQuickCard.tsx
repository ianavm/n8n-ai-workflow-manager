import Link from "next/link";
import {
  Megaphone,
  Calculator,
  FileText,
  Users,
  type LucideIcon,
} from "lucide-react";

type ModuleType = "marketing" | "accounting" | "content" | "leads";

interface ModuleQuickCardProps {
  module: ModuleType;
  metrics: Record<string, number | string>;
  href: string;
}

interface ModuleConfig {
  icon: LucideIcon;
  color: string;
  label: string;
}

const MODULE_CONFIG: Record<ModuleType, ModuleConfig> = {
  marketing: { icon: Megaphone, color: "#FF6D5A", label: "Marketing" },
  accounting: { icon: Calculator, color: "#00D4AA", label: "Accounting" },
  content: { icon: FileText, color: "#6C63FF", label: "Content" },
  leads: { icon: Users, color: "#10B981", label: "Leads" },
};

export function ModuleQuickCard({
  module,
  metrics,
  href,
}: ModuleQuickCardProps) {
  const config = MODULE_CONFIG[module];
  const IconComponent = config.icon;
  const metricEntries = Object.entries(metrics).slice(0, 3);

  return (
    <div
      className="glass-card"
      style={{
        width: "260px",
        minWidth: "260px",
        padding: "20px",
        display: "flex",
        flexDirection: "column",
        gap: "14px",
        transition: "transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.3s ease",
        cursor: "pointer",
      }}
      onMouseEnter={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(-4px)";
        (e.currentTarget as HTMLElement).style.boxShadow = `0 8px 32px ${config.color}15`;
      }}
      onMouseLeave={(e) => {
        (e.currentTarget as HTMLElement).style.transform = "translateY(0)";
        (e.currentTarget as HTMLElement).style.boxShadow = "none";
      }}
    >
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
        <div
          style={{
            width: "36px",
            height: "36px",
            borderRadius: "50%",
            background: `${config.color}20`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}
        >
          <IconComponent size={18} color={config.color} />
        </div>
        <span style={{ fontSize: "15px", fontWeight: 600, color: "#fff" }}>
          {config.label}
        </span>
      </div>

      {/* Metrics */}
      <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
        {metricEntries.map(([key, val]) => (
          <div
            key={key}
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <span style={{ fontSize: "13px", color: "#6B7280" }}>{key}</span>
            <span style={{ fontSize: "13px", fontWeight: 600, color: "#fff" }}>
              {typeof val === "number" ? val.toLocaleString("en-ZA") : val}
            </span>
          </div>
        ))}
      </div>

      {/* Link */}
      <Link
        href={href}
        style={{
          fontSize: "13px",
          fontWeight: 600,
          color: config.color,
          textDecoration: "none",
          marginTop: "auto",
          transition: "opacity 0.2s ease",
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLElement).style.opacity = "0.8";
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLElement).style.opacity = "1";
        }}
      >
        View &rarr;
      </Link>
    </div>
  );
}
