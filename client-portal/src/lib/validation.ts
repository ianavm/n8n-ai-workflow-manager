// Shared validation utilities

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function isValidUUID(value: unknown): value is string {
  return typeof value === "string" && UUID_REGEX.test(value);
}

export function validatePassword(password: string): string | null {
  if (password.length < 8) return "Password must be at least 8 characters";
  if (!/[A-Z]/.test(password)) return "Password must contain an uppercase letter";
  if (!/[a-z]/.test(password)) return "Password must contain a lowercase letter";
  if (!/[0-9]/.test(password)) return "Password must contain a number";
  if (!/[!@#$%^&*(),.?":{}|<>]/.test(password))
    return "Password must contain a special character (!@#$%^&* etc.)";
  return null;
}

const VALID_CLIENT_STATUSES = ["active", "suspended", "inactive"] as const;

export function isValidClientStatus(
  status: unknown
): status is (typeof VALID_CLIENT_STATUSES)[number] {
  return (
    typeof status === "string" &&
    VALID_CLIENT_STATUSES.includes(status as (typeof VALID_CLIENT_STATUSES)[number])
  );
}

const MAX_METADATA_SIZE = 8192; // 8KB

export function sanitizeMetadata(metadata: unknown): Record<string, unknown> {
  if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
    return {};
  }
  const json = JSON.stringify(metadata);
  if (json.length > MAX_METADATA_SIZE) {
    return { _error: "metadata too large, truncated", _size: json.length };
  }
  return metadata as Record<string, unknown>;
}

export function extractClientIp(request: Request): string {
  const forwarded = request.headers.get("x-forwarded-for");
  if (!forwarded) return "unknown";
  // Use only the first IP (the actual client), ignore proxy chain
  return forwarded.split(",")[0].trim();
}
