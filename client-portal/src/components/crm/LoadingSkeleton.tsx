interface SkeletonProps {
  className?: string;
  height?: number;
  width?: number | string;
  rounded?: "sm" | "md" | "lg" | "full";
}

export function Skeleton({ className, height = 14, width, rounded = "md" }: SkeletonProps) {
  const r =
    rounded === "full"
      ? "rounded-full"
      : rounded === "lg"
        ? "rounded-lg"
        : rounded === "md"
          ? "rounded-md"
          : "rounded-sm";
  return (
    <div
      className={`animate-pulse bg-[rgba(255,255,255,0.06)] ${r} ${className ?? ""}`}
      style={{ height, width }}
    />
  );
}

export function SkeletonKpiStrip() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div
          key={i}
          className="rounded-xl border bg-[#121827] border-[rgba(255,255,255,0.07)] p-5"
        >
          <Skeleton height={10} width={80} />
          <div className="mt-3"><Skeleton height={28} width={120} /></div>
          <div className="mt-2"><Skeleton height={10} width={60} /></div>
        </div>
      ))}
    </div>
  );
}

export function SkeletonTableRows({ rows = 10, columns = 6 }: { rows?: number; columns?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="grid grid-cols-12 gap-3 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.02)]">
          {Array.from({ length: columns }).map((_, c) => (
            <div key={c} className={c === 0 ? "col-span-3" : "col-span-2"}>
              <Skeleton height={12} width={c === 0 ? "70%" : "50%"} />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
