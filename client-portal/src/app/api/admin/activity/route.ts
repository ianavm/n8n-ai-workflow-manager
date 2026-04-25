import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const MAX_LIMIT = 200;

export async function GET(request: NextRequest) {
  const session = await getSession();
  if (!session || (session.role !== "superior_admin" && session.role !== "staff_admin")) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { searchParams } = new URL(request.url);
  const limit = Math.min(
    Math.max(parseInt(searchParams.get("limit") || "50") || 50, 1),
    MAX_LIMIT
  );
  const offset = Math.max(parseInt(searchParams.get("offset") || "0") || 0, 0);
  const actorType = searchParams.get("actor_type");

  const supabase = await createServiceRoleClient();

  let query = supabase
    .from("activity_log")
    .select("*")
    .order("created_at", { ascending: false })
    .range(offset, offset + limit - 1);

  if (actorType && ["admin", "client", "system", "api"].includes(actorType)) {
    query = query.eq("actor_type", actorType);
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json({ error: "Failed to fetch activity log" }, { status: 500 });
  }

  return NextResponse.json(data);
}
