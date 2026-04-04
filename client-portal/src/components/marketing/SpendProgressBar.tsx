interface SpendProgressBarProps {
  spent: number;
  budget: number;
  label?: string;
}

export function SpendProgressBar({ spent, budget, label }: SpendProgressBarProps) {
  const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
  const color =
    pct >= 90 ? "#EF4444" : pct >= 70 ? "#F97316" : "#10B981";

  return (
    <div className="space-y-1">
      {label && (
        <div className="flex justify-between text-xs text-[#B0B8C8]">
          <span>{label}</span>
          <span>
            R{(spent / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })} / R{(budget / 100).toLocaleString("en-ZA", { minimumFractionDigits: 0 })}
          </span>
        </div>
      )}
      <div className="h-2 rounded-full bg-[rgba(255,255,255,0.06)] overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}
