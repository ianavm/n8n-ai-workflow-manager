"use client";

import Link from "next/link";

export default function AdminError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] px-6 text-center">
      <div
        className="w-16 h-16 rounded-2xl flex items-center justify-center mb-6"
        style={{
          background: "rgba(255, 109, 90, 0.1)",
          border: "1px solid rgba(255, 109, 90, 0.2)",
        }}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="#FF6D5A"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
      </div>
      <h1 className="text-2xl font-bold text-white mb-2">
        Admin Error
      </h1>
      <p className="text-sm text-[var(--text-dim)] mb-8 max-w-md">
        {error.message || "Something went wrong in the admin panel."}
      </p>
      <div className="flex items-center gap-4">
        <button
          onClick={reset}
          className="px-6 py-3 rounded-xl text-sm font-semibold text-white transition-opacity hover:opacity-90"
          style={{ background: "linear-gradient(135deg, #FF6D5A, #FF8A6B)" }}
        >
          Try Again
        </button>
        <Link
          href="/"
          className="px-6 py-3 rounded-xl text-sm font-medium text-[var(--text-muted)] transition-colors hover:text-white"
          style={{
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
          }}
        >
          Go Home
        </Link>
      </div>
    </div>
  );
}
