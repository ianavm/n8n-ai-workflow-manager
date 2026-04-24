import { cn } from "@/lib/utils";

interface BlobBackgroundProps {
  intensity?: "hero" | "subtle" | "off";
  className?: string;
}

const baseBlob =
  "pointer-events-none absolute rounded-full filter blur-[120px] mix-blend-normal";

/**
 * Absolutely-positioned animated color blobs. Drops into any hero region
 * to evoke the marketing site's signature ambient glow. Parent must be
 * `relative` + `overflow-hidden`. Blobs are hidden when
 * `prefers-reduced-motion: reduce`.
 */
export function BlobBackground({ intensity = "subtle", className }: BlobBackgroundProps) {
  if (intensity === "off") return null;

  const hero = intensity === "hero";

  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)} aria-hidden>
      <div
        className={cn(
          baseBlob,
          hero ? "size-[520px] opacity-40" : "size-[320px] opacity-20",
          "-top-20 -left-24 bg-[var(--accent-purple)] motion-safe:animate-[blobFloat1_12s_ease-in-out_infinite]",
        )}
      />
      <div
        className={cn(
          baseBlob,
          hero ? "size-[460px] opacity-35" : "size-[280px] opacity-20",
          "top-10 right-0 bg-[var(--accent-teal)] motion-safe:animate-[blobFloat2_15s_ease-in-out_infinite]",
        )}
      />
      <div
        className={cn(
          baseBlob,
          hero ? "size-[420px] opacity-30" : "size-[260px] opacity-15",
          "-bottom-24 left-1/3 bg-[var(--accent-coral)] motion-safe:animate-[blobFloat3_18s_ease-in-out_infinite]",
        )}
      />
    </div>
  );
}
