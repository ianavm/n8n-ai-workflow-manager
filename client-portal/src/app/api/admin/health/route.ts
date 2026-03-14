import { NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.SUPABASE_SERVICE_ROLE_KEY!
);

export async function GET() {
  const [healthRes, renewalRes, clientsRes] = await Promise.all([
    supabase
      .from("client_health_scores")
      .select("*")
      .order("composite_score", { ascending: true }),
    supabase
      .from("renewal_pipeline")
      .select("*")
      .order("days_until_renewal", { ascending: true }),
    supabase
      .from("clients")
      .select("id, company_name, email"),
  ]);

  return NextResponse.json({
    healthScores: healthRes.data || [],
    renewals: renewalRes.data || [],
    clients: clientsRes.data || [],
  });
}
