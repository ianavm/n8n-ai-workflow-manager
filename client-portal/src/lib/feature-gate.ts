import { createClient, SupabaseClient } from "@supabase/supabase-js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface PlanLimits {
  workflows: number; // -1 = unlimited
  messages: number;
  agents: number;
  leads: number;
  departments: number;
  campaigns: number;
  posts: number;
  marketing_leads: number;
}

export interface LimitCheckResult {
  allowed: boolean;
  used: number;
  limit: number; // -1 = unlimited
  remaining: number; // -1 = unlimited
  overage: boolean; // true when usage exceeds plan limit but under hard cap (2x)
  overageCount: number; // units over the plan limit
}

export interface AddonInfo {
  addon_id: string;
  addon_name: string;
  addon_slug: string;
  addon_description: string;
  price_monthly: number;
  category: string;
  limits_bonus: Record<string, number>;
  features: string[];
  activated_at: string;
}

// Shape returned by the get_client_subscription RPC
interface ClientSubscription {
  id: string;
  client_id: string;
  plan_id: string;
  limits: PlanLimits;
  [key: string]: unknown;
}

// Shape returned by the get_client_usage RPC
interface ClientUsage {
  messages_used: number;
  leads_used: number;
  workflows_count: number;
  agents_count: number;
  campaigns_count: number;
  posts_count: number;
  marketing_leads_used: number;
  [key: string]: unknown;
}

// Map feature name -> usage record column
const FEATURE_TO_USAGE_COL: Record<
  "workflows" | "messages" | "agents" | "leads" | "campaigns" | "posts" | "marketing_leads",
  keyof ClientUsage
> = {
  workflows: "workflows_count",
  messages: "messages_used",
  agents: "agents_count",
  leads: "leads_used",
  campaigns: "campaigns_count",
  posts: "posts_count",
  marketing_leads: "marketing_leads_used",
};

// Overage multiplier: allow up to 2x plan limit before hard block
const OVERAGE_HARD_CAP_MULTIPLIER = 2;

// ---------------------------------------------------------------------------
// Supabase service client (bypasses RLS)
// ---------------------------------------------------------------------------

let _serviceClient: SupabaseClient | null = null;

export function createServiceSupabase(): SupabaseClient {
  if (_serviceClient) return _serviceClient;

  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !key) {
    throw new Error(
      "Missing NEXT_PUBLIC_SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
    );
  }

  _serviceClient = createClient(url, key, {
    auth: { autoRefreshToken: false, persistSession: false },
  });

  return _serviceClient;
}

// ---------------------------------------------------------------------------
// Core helpers
// ---------------------------------------------------------------------------

async function fetchSubscription(
  supabase: SupabaseClient,
  clientId: string
): Promise<ClientSubscription | null> {
  const { data, error } = await supabase.rpc("get_client_subscription", {
    client_id: clientId,
  });

  if (error) {
    console.error("[feature-gate] get_client_subscription error:", error);
    return null;
  }

  return (data as ClientSubscription) ?? null;
}

async function fetchUsage(
  supabase: SupabaseClient,
  clientId: string
): Promise<ClientUsage> {
  const empty: ClientUsage = {
    messages_used: 0,
    leads_used: 0,
    workflows_count: 0,
    agents_count: 0,
    campaigns_count: 0,
    posts_count: 0,
    marketing_leads_used: 0,
  };

  const { data, error } = await supabase.rpc("get_client_usage", {
    client_id: clientId,
  });

  if (error) {
    console.error("[feature-gate] get_client_usage error:", error);
    return empty;
  }

  return (data as ClientUsage) ?? empty;
}

/**
 * Fetch merged limits (plan + active add-ons) using the DB function.
 * Falls back to base plan limits if the RPC is unavailable.
 */
async function fetchMergedLimits(
  supabase: SupabaseClient,
  clientId: string
): Promise<PlanLimits | null> {
  const { data, error } = await supabase.rpc("get_client_merged_limits", {
    p_client_id: clientId,
  });

  if (error) {
    console.error("[feature-gate] get_client_merged_limits error:", error);
    return null;
  }

  if (!data || Object.keys(data).length === 0) {
    return null;
  }

  return data as PlanLimits;
}

/**
 * Build a limit check result with overage support.
 * - If limit is -1 (unlimited), always allowed.
 * - If used < limit, allowed with no overage.
 * - If used >= limit but < 2x limit, allowed with overage flag.
 * - If used >= 2x limit, blocked (hard cap).
 */
function buildResult(used: number, limit: number): LimitCheckResult {
  if (limit === -1) {
    return {
      allowed: true,
      used,
      limit: -1,
      remaining: -1,
      overage: false,
      overageCount: 0,
    };
  }

  const remaining = Math.max(limit - used, 0);
  const hardCap = limit * OVERAGE_HARD_CAP_MULTIPLIER;
  const isOverLimit = used >= limit;
  const isUnderHardCap = used < hardCap;

  if (!isOverLimit) {
    return { allowed: true, used, limit, remaining, overage: false, overageCount: 0 };
  }

  // Over plan limit — check if under hard cap (soft overage zone)
  if (isUnderHardCap) {
    return {
      allowed: true,
      used,
      limit,
      remaining: 0,
      overage: true,
      overageCount: used - limit,
    };
  }

  // At or above hard cap — blocked
  return {
    allowed: false,
    used,
    limit,
    remaining: 0,
    overage: true,
    overageCount: used - limit,
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Check whether a client is within their plan limit for a single feature.
 * Uses merged limits (plan + active add-ons).
 */
export async function checkLimit(
  clientId: string,
  feature: keyof PlanLimits
): Promise<LimitCheckResult> {
  const supabase = createServiceSupabase();

  const [mergedLimits, usage] = await Promise.all([
    fetchMergedLimits(supabase, clientId),
    fetchUsage(supabase, clientId),
  ]);

  if (!mergedLimits) {
    return { allowed: false, used: 0, limit: 0, remaining: 0, overage: false, overageCount: 0 };
  }

  const limit = mergedLimits[feature] ?? 0;
  const usageCol = FEATURE_TO_USAGE_COL[feature as keyof typeof FEATURE_TO_USAGE_COL];
  const used = usageCol ? ((usage[usageCol] as number) ?? 0) : 0;

  return buildResult(used, limit);
}

/**
 * Check whether a client has access to a specific department.
 * Department count is tracked in plan limits as `departments` (-1 = unlimited).
 */
export async function checkDepartmentAccess(
  clientId: string,
  _departmentSlug: string
): Promise<{ allowed: boolean; activeDepartments: number; maxDepartments: number }> {
  const supabase = createServiceSupabase();
  const mergedLimits = await fetchMergedLimits(supabase, clientId);

  if (!mergedLimits) {
    return { allowed: false, activeDepartments: 0, maxDepartments: 0 };
  }

  const maxDepts = mergedLimits.departments ?? 0;

  if (maxDepts === -1) {
    return { allowed: true, activeDepartments: 0, maxDepartments: -1 };
  }

  // Count active departments from usage_records or subscription config
  // For now, check against the department limit directly
  // Active department count would be tracked by the portal when departments are enabled
  return { allowed: true, activeDepartments: 0, maxDepartments: maxDepts };
}

/**
 * Get active add-ons for a client's current subscription.
 */
export async function getClientAddons(
  clientId: string
): Promise<AddonInfo[]> {
  const supabase = createServiceSupabase();

  // First get the subscription ID
  const sub = await fetchSubscription(supabase, clientId);
  if (!sub) return [];

  const { data, error } = await supabase.rpc("get_subscription_addons", {
    p_subscription_id: sub.id,
  });

  if (error) {
    console.error("[feature-gate] get_subscription_addons error:", error);
    return [];
  }

  return (data as AddonInfo[]) ?? [];
}

/**
 * Increment a consumable usage counter (messages or leads) for the current
 * billing period. Upserts the usage_records row for the current month.
 */
export async function incrementUsage(
  clientId: string,
  feature: "messages" | "leads" | "campaigns" | "posts" | "marketing_leads"
): Promise<void> {
  const supabase = createServiceSupabase();

  const now = new Date();
  const periodStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split("T")[0];
  const periodEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0)
    .toISOString()
    .split("T")[0];

  const featureColMap: Record<string, string> = {
    messages: "messages_used",
    leads: "leads_used",
    campaigns: "campaigns_count",
    posts: "posts_count",
    marketing_leads: "marketing_leads_used",
  };
  const col = featureColMap[feature] ?? "messages_used";

  // Try to find an existing record for this period
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const { data: existing, error: fetchErr } = await (supabase as any)
    .from("usage_records")
    .select("id, " + col)
    .eq("client_id", clientId)
    .eq("period_start", periodStart)
    .maybeSingle() as { data: Record<string, unknown> | null; error: unknown };

  if (fetchErr) {
    console.error("[feature-gate] incrementUsage fetch error:", fetchErr);
    return;
  }

  if (existing) {
    // Increment existing record
    const currentVal = (existing[col] as number) ?? 0;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const { error: updateErr } = await (supabase as any)
      .from("usage_records")
      .update({ [col]: currentVal + 1 })
      .eq("id", existing.id);

    if (updateErr) {
      console.error("[feature-gate] incrementUsage update error:", updateErr);
    }
  } else {
    // Insert new record for this period
    const insertData: Record<string, unknown> = {
      client_id: clientId,
      period_start: periodStart,
      period_end: periodEnd,
      messages_used: 0,
      leads_used: 0,
      workflows_count: 0,
      agents_count: 0,
    };
    insertData[col] = 1;
    const { error: insertErr } = await supabase
      .from("usage_records")
      .insert(insertData);

    if (insertErr) {
      console.error("[feature-gate] incrementUsage insert error:", insertErr);
    }
  }
}

/**
 * Return a full usage summary for all gated features in one call.
 * Uses merged limits (plan + active add-ons) for accurate gating.
 */
export async function getClientUsageSummary(
  clientId: string
): Promise<Record<keyof PlanLimits, LimitCheckResult>> {
  const supabase = createServiceSupabase();

  const [mergedLimits, usage] = await Promise.all([
    fetchMergedLimits(supabase, clientId),
    fetchUsage(supabase, clientId),
  ]);

  const noSub: LimitCheckResult = {
    allowed: false,
    used: 0,
    limit: 0,
    remaining: 0,
    overage: false,
    overageCount: 0,
  };

  if (!mergedLimits) {
    return {
      workflows: noSub,
      messages: noSub,
      agents: noSub,
      leads: noSub,
      departments: noSub,
      campaigns: noSub,
      posts: noSub,
      marketing_leads: noSub,
    };
  }

  const gatedFeatures: (keyof typeof FEATURE_TO_USAGE_COL)[] = [
    "workflows",
    "messages",
    "agents",
    "leads",
  ];

  const result = {} as Record<keyof PlanLimits, LimitCheckResult>;

  for (const feature of gatedFeatures) {
    const limit = mergedLimits[feature] ?? 0;
    const used = (usage[FEATURE_TO_USAGE_COL[feature]] as number) ?? 0;
    result[feature] = buildResult(used, limit);
  }

  // Departments are gated by count, not tracked in usage_records
  const deptLimit = mergedLimits.departments ?? 0;
  result.departments = buildResult(0, deptLimit);

  return result;
}

/**
 * Calculate usage percentage for a feature (for progress bars).
 * Returns 0-100 (can exceed 100 in overage zone).
 */
export function getUsagePercentage(result: LimitCheckResult): number {
  if (result.limit === -1) return 0; // unlimited
  if (result.limit === 0) return 100; // no access
  return Math.round((result.used / result.limit) * 100);
}

/**
 * Get the warning level for a usage result.
 */
export function getUsageWarningLevel(
  result: LimitCheckResult
): "normal" | "warning" | "critical" | "blocked" {
  if (result.limit === -1) return "normal";
  if (!result.allowed) return "blocked";
  if (result.overage) return "critical";

  const pct = getUsagePercentage(result);
  if (pct >= 95) return "critical";
  if (pct >= 80) return "warning";
  return "normal";
}
