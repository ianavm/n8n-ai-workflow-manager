"use client";

import { AlertTriangle, RotateCcw } from "lucide-react";
import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Surface errors to a logging backend in real deployment; leave as-is for now.
  }, [error]);

  return (
    <div className="flex flex-col items-center justify-center text-center py-16 px-6 rounded-xl border border-[rgba(239,68,68,0.25)] bg-[rgba(239,68,68,0.05)]">
      <div className="w-12 h-12 rounded-full grid place-items-center bg-[rgba(239,68,68,0.12)] border border-[rgba(239,68,68,0.35)]">
        <AlertTriangle size={20} color="#EF4444" />
      </div>
      <h3 className="mt-4 text-[15px] font-semibold text-white">Something went wrong</h3>
      <p className="mt-1 max-w-md text-sm text-[#B0B8C8]">
        We couldn&apos;t load this part of your CRM. This was logged — you can try again or
        refresh the page.
      </p>
      <button
        onClick={reset}
        className="mt-5 inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white border border-[rgba(255,255,255,0.12)] hover:bg-[rgba(255,255,255,0.05)] transition-colors"
      >
        <RotateCcw size={14} />
        Try again
      </button>
    </div>
  );
}
