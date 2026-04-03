interface PaymentStatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  received: { label: "Received", color: "text-blue-300", bg: "bg-blue-500/20" },
  matching: { label: "Matching", color: "text-yellow-300", bg: "bg-yellow-500/20" },
  matched: { label: "Matched", color: "text-green-300", bg: "bg-green-500/20" },
  partial: { label: "Partial Match", color: "text-amber-300", bg: "bg-amber-500/20" },
  unmatched: { label: "Unmatched", color: "text-red-300", bg: "bg-red-500/20" },
  reconciled: { label: "Reconciled", color: "text-emerald-300", bg: "bg-emerald-500/20" },
  overpayment: { label: "Overpayment", color: "text-purple-300", bg: "bg-purple-500/20" },
};

export function PaymentStatusBadge({ status }: PaymentStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, color: "text-gray-300", bg: "bg-gray-500/20" };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
      {config.label}
    </span>
  );
}
