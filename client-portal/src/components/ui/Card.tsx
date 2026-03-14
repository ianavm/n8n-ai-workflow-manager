"use client";

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  variant?: "default" | "gradient" | "floating";
  padding?: "none" | "sm" | "md" | "lg";
}

export function Card({
  children,
  className = "",
  hover = true,
  variant = "default",
  padding = "md",
}: CardProps) {
  const padMap = { none: "0", sm: "16px", md: "24px", lg: "32px" };
  const pad = padMap[padding];

  if (variant === "gradient") {
    return (
      <div
        style={{
          position: "relative",
          borderRadius: "16px",
          padding: "1px",
          overflow: "hidden",
          background: "linear-gradient(135deg, rgba(108,99,255,0.25), rgba(0,212,170,0.15))",
        }}
      >
        <div
          className={className}
          style={{
            position: "relative",
            borderRadius: "16px",
            background: "rgba(10,15,28,0.95)",
            backdropFilter: "blur(20px)",
            WebkitBackdropFilter: "blur(20px)",
            padding: pad,
          }}
        >
          {children}
        </div>
      </div>
    );
  }

  if (variant === "floating") {
    return (
      <div className={`floating-card ${className}`} style={{ padding: pad }}>
        {children}
      </div>
    );
  }

  return (
    <div
      className={`${hover ? "glass-card" : "glass-card-static"} ${className}`}
      style={{ padding: pad }}
    >
      {children}
    </div>
  );
}
