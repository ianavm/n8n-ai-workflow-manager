import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface ScoreDetails {
  usage_score: number;
  payment_score: number;
  engagement_score: number;
  support_score: number;
}

function buildTips(scores: ScoreDetails): string[] {
  const dimensions: { key: keyof ScoreDetails; tip: string }[] = [
    {
      key: "usage_score",
      tip: "Log in regularly and explore all your automation modules",
    },
    {
      key: "payment_score",
      tip: "Keep your subscription payments current for uninterrupted service",
    },
    {
      key: "engagement_score",
      tip: "Publish content and respond to leads to boost your growth activity",
    },
    {
      key: "support_score",
      tip: "Resolve open support tickets to improve your support experience",
    },
  ];

  const sorted = [...dimensions].sort(
    (a, b) => (scores[a.key] ?? 100) - (scores[b.key] ?? 100)
  );

  const tips: string[] = [];
  for (const dim of sorted) {
    if ((scores[dim.key] ?? 100) < 80) {
      tips.push(dim.tip);
    }
    if (tips.length >= 3) break;
  }

  if (tips.length === 0) {
    tips.push("Great job! Your business health looks excellent across all areas.");
  }

  return tips;
}

export async function GET() {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.profileId;
  const supabase = await createServiceRoleClient();

  const { data: rpcResult, error: rpcError } = await supabase.rpc(
    "get_client_health_details",
    { p_client_id: clientId }
  );

  if (rpcError) {
    if (rpcError.code === "42883") {
      // RPC function doesn't exist yet — return empty
      return NextResponse.json({ health: null, tips: [] });
    }
    return NextResponse.json(
      { error: "Failed to load health data" },
      { status: 500 }
    );
  }

  const health = rpcResult ?? null;
  const current = health?.current as ScoreDetails | null;

  const tips = current
    ? buildTips(current)
    : ["No health data available yet. Your scores will populate soon."];

  return NextResponse.json({ health, tips });
}
