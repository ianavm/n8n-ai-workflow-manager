"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body style={{ margin: 0, background: "#0A0F1C", fontFamily: "Inter, system-ui, sans-serif" }}>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100vh",
            padding: "24px",
            textAlign: "center",
          }}
        >
          <div
            style={{
              width: "64px",
              height: "64px",
              borderRadius: "16px",
              background: "rgba(255, 109, 90, 0.1)",
              border: "1px solid rgba(255, 109, 90, 0.2)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: "24px",
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
          <h1 style={{ fontSize: "24px", fontWeight: 700, color: "#fff", marginBottom: "8px" }}>
            Something went wrong
          </h1>
          <p style={{ fontSize: "14px", color: "#6B7280", marginBottom: "32px", maxWidth: "400px" }}>
            {error.message || "A critical error occurred. Please try again."}
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <button
              onClick={reset}
              style={{
                padding: "12px 24px",
                borderRadius: "12px",
                fontSize: "14px",
                fontWeight: 600,
                color: "#fff",
                background: "linear-gradient(135deg, #FF6D5A, #FF8A6B)",
                border: "none",
                cursor: "pointer",
              }}
            >
              Try Again
            </button>
            <a
              href="/"
              style={{
                padding: "12px 24px",
                borderRadius: "12px",
                fontSize: "14px",
                fontWeight: 500,
                color: "#B0B8C8",
                background: "rgba(255,255,255,0.05)",
                border: "1px solid rgba(255,255,255,0.1)",
                textDecoration: "none",
              }}
            >
              Go Home
            </a>
          </div>
        </div>
      </body>
    </html>
  );
}
