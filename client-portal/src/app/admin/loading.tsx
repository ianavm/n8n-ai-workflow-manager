export default function AdminLoading() {
  return (
    <div className="space-y-6 max-w-[1200px] animate-pulse">
      {/* Welcome banner skeleton */}
      <div
        className="rounded-2xl p-8 h-40"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="h-7 w-64 rounded-lg bg-[rgba(255,255,255,0.06)] mb-3" />
        <div className="h-4 w-48 rounded bg-[rgba(255,255,255,0.04)] mb-2" />
        <div className="h-4 w-56 rounded bg-[rgba(255,255,255,0.04)]" />
      </div>

      {/* Stat cards skeleton */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="rounded-2xl p-6 h-36"
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="w-12 h-12 rounded-xl bg-[rgba(255,255,255,0.06)] mb-4" />
            <div className="h-8 w-16 rounded-lg bg-[rgba(255,255,255,0.08)] mb-2" />
            <div className="h-4 w-24 rounded bg-[rgba(255,255,255,0.04)]" />
          </div>
        ))}
      </div>

      {/* Table skeleton */}
      <div
        className="rounded-2xl p-6"
        style={{
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        <div className="h-5 w-40 rounded bg-[rgba(255,255,255,0.06)] mb-6" />
        <div className="space-y-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center gap-4">
              <div className="h-4 w-32 rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-20 rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-16 rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-24 rounded bg-[rgba(255,255,255,0.04)]" />
              <div className="h-4 w-16 rounded bg-[rgba(255,255,255,0.04)]" />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
