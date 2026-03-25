export default function PortalLoading() {
  return (
    <div className="space-y-8 animate-pulse">
      {/* Top bar skeleton */}
      <div className="flex items-center justify-between">
        <div>
          <div className="h-7 w-56 rounded-lg bg-[rgba(255,255,255,0.06)]" />
          <div className="h-4 w-80 rounded-lg bg-[rgba(255,255,255,0.04)] mt-2" />
        </div>
        <div className="h-10 w-32 rounded-xl bg-[rgba(255,255,255,0.06)]" />
      </div>

      {/* Stat cards skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-7">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-2xl p-6"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="h-5 w-24 rounded bg-[rgba(255,255,255,0.06)] mb-4" />
            <div className="h-9 w-20 rounded-lg bg-[rgba(255,255,255,0.08)]" />
          </div>
        ))}
      </div>

      {/* Chart grid skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-7">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-2xl p-6 h-64"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="h-5 w-36 rounded bg-[rgba(255,255,255,0.06)] mb-4" />
            <div className="h-4 w-24 rounded bg-[rgba(255,255,255,0.04)] mb-6" />
            <div className="h-32 w-full rounded-xl bg-[rgba(255,255,255,0.04)]" />
          </div>
        ))}
      </div>

      {/* Bottom row skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-7">
        {[1, 2, 3].map((i) => (
          <div
            key={i}
            className="rounded-2xl p-6 h-48"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="h-5 w-32 rounded bg-[rgba(255,255,255,0.06)] mb-4" />
            <div className="space-y-3">
              <div className="h-4 w-full rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-3/4 rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-5/6 rounded bg-[rgba(255,255,255,0.04)]" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
