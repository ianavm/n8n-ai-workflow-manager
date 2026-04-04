interface CampaignStatusBadgeProps {
  status: string;
}

const STATUS_STYLES: Record<string, { bg: string; text: string; label: string }> = {
  draft: { bg: "rgba(107,114,128,0.15)", text: "#9CA3AF", label: "Draft" },
  pending_review: { bg: "rgba(234,179,8,0.15)", text: "#EAB308", label: "Pending Review" },
  approved: { bg: "rgba(59,130,246,0.15)", text: "#3B82F6", label: "Approved" },
  active: { bg: "rgba(16,185,129,0.15)", text: "#10B981", label: "Active" },
  paused: { bg: "rgba(249,115,22,0.15)", text: "#F97316", label: "Paused" },
  completed: { bg: "rgba(108,99,255,0.15)", text: "#6C63FF", label: "Completed" },
  archived: { bg: "rgba(107,114,128,0.1)", text: "#6B7280", label: "Archived" },
};

export function CampaignStatusBadge({ status }: CampaignStatusBadgeProps) {
  const style = STATUS_STYLES[status] ?? STATUS_STYLES.draft;

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium"
      style={{ background: style.bg, color: style.text }}
    >
      {style.label}
    </span>
  );
}
