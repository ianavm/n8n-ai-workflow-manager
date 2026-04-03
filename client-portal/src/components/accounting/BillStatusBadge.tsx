interface BillStatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  uploaded: { label: "Uploaded", color: "text-gray-300", bg: "bg-gray-500/20" },
  extracted: { label: "Extracted", color: "text-blue-300", bg: "bg-blue-500/20" },
  awaiting_review: { label: "Awaiting Review", color: "text-yellow-300", bg: "bg-yellow-500/20" },
  approved: { label: "Approved", color: "text-green-300", bg: "bg-green-500/20" },
  scheduled: { label: "Scheduled", color: "text-cyan-300", bg: "bg-cyan-500/20" },
  paid: { label: "Paid", color: "text-emerald-300", bg: "bg-emerald-500/20" },
  rejected: { label: "Rejected", color: "text-red-300", bg: "bg-red-500/20" },
};

export function BillStatusBadge({ status }: BillStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, color: "text-gray-300", bg: "bg-gray-500/20" };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
      {config.label}
    </span>
  );
}
