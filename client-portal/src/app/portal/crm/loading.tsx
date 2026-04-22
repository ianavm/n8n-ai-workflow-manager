import { SkeletonKpiStrip, SkeletonTableRows } from "@/components/crm/LoadingSkeleton";

export default function Loading() {
  return (
    <div className="space-y-6">
      <SkeletonKpiStrip />
      <div className="rounded-xl border bg-[#121827] border-[rgba(255,255,255,0.07)] p-5">
        <SkeletonTableRows rows={8} columns={6} />
      </div>
    </div>
  );
}
