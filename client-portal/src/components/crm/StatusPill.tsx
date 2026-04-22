interface StatusPillProps {
  label: string;
  color?: string | null;
  size?: "sm" | "md";
}

export function StatusPill({ label, color, size = "sm" }: StatusPillProps) {
  const accent = color ?? "#71717A";
  const style = {
    background: `${accent}22`,
    borderColor: `${accent}55`,
    color: accent,
  };
  const sizeClasses =
    size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium whitespace-nowrap ${sizeClasses}`}
      style={style}
    >
      <span
        aria-hidden
        className="w-1.5 h-1.5 rounded-full"
        style={{ background: accent }}
      />
      {label}
    </span>
  );
}
