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
  const padMap = { none: "0", sm: "20px", md: "28px", lg: "36px" };
  const pad = padMap[padding];

  if (variant === "gradient") {
    return (
      <div
        className={`glass-card ${className}`}
        style={{
          padding: pad,
          borderLeft: "3px solid var(--brand-primary)",
        }}
      >
        {children}
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
