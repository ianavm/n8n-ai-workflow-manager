interface LeadScoreBadgeProps {
  score: number;
}

function getScoreColor(score: number): string {
  if (score <= 30) return "#EF4444";
  if (score <= 60) return "#F59E0B";
  return "#10B981";
}

export function LeadScoreBadge({ score }: LeadScoreBadgeProps) {
  const color = getScoreColor(score);

  return (
    <span
      className="inline-flex items-center justify-center w-9 h-9 rounded-full text-xs font-bold"
      style={{
        color,
        backgroundColor: `${color}26`,
      }}
    >
      {score}
    </span>
  );
}
