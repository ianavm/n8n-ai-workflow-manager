import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

const querySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(200).default(50),
  q: z.string().trim().optional(),
  stage: z.string().trim().optional(),
  minScore: z.coerce.number().int().min(0).max(100).optional(),
  maxScore: z.coerce.number().int().min(0).max(100).optional(),
  client: z.string().uuid().optional(),
});

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const parsed = querySchema.safeParse(Object.fromEntries(url.searchParams));
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid query" }, { status: 400 });
  }
  const { page, pageSize, q, stage, minScore, maxScore, client } = parsed.data;

  const ctx = await getCrmViewerContext(client);
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });

  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass ?client=<uuid>" },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();
  const from = (page - 1) * pageSize;
  const to = from + pageSize - 1;

  let query = supabase
    .from("crm_leads")
    .select(
      `
        id, stage_key, score, status_tags, tags, source, created_at, updated_at, last_touch_at, deal_value_zar,
        company:crm_companies ( id, name, industry, country, logo_url ),
        contact:crm_contacts ( id, first_name, last_name, email, title )
      `,
      { count: "exact" },
    )
    .eq("client_id", clientId)
    .order("created_at", { ascending: false })
    .range(from, to);

  if (q) query = query.ilike("crm_companies.name", `%${q}%`);
  if (stage) query = query.eq("stage_key", stage);
  if (minScore !== undefined) query = query.gte("score", minScore);
  if (maxScore !== undefined) query = query.lte("score", maxScore);

  const { data, count, error } = await query;
  if (error) {
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    success: true,
    data: data ?? [],
    meta: { total: count ?? 0, page, limit: pageSize },
  });
}
