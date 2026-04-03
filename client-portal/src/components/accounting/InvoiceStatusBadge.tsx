interface InvoiceStatusBadgeProps {
  status: string;
}

const STATUS_CONFIG: Record<string, { label: string; color: string; bg: string }> = {
  draft: { label: "Draft", color: "text-gray-300", bg: "bg-gray-500/20" },
  approved: { label: "Approved", color: "text-blue-300", bg: "bg-blue-500/20" },
  sent: { label: "Sent", color: "text-cyan-300", bg: "bg-cyan-500/20" },
  viewed: { label: "Viewed", color: "text-indigo-300", bg: "bg-indigo-500/20" },
  payment_pending: { label: "Payment Pending", color: "text-yellow-300", bg: "bg-yellow-500/20" },
  partially_paid: { label: "Partially Paid", color: "text-amber-300", bg: "bg-amber-500/20" },
  paid: { label: "Paid", color: "text-green-300", bg: "bg-green-500/20" },
  overdue: { label: "Overdue", color: "text-red-300", bg: "bg-red-500/20" },
  disputed: { label: "Disputed", color: "text-orange-300", bg: "bg-orange-500/20" },
  cancelled: { label: "Cancelled", color: "text-gray-400", bg: "bg-gray-600/20" },
};

export function InvoiceStatusBadge({ status }: InvoiceStatusBadgeProps) {
  const config = STATUS_CONFIG[status] ?? { label: status, color: "text-gray-300", bg: "bg-gray-500/20" };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${config.color} ${config.bg}`}>
      {config.label}
    </span>
  );
}
