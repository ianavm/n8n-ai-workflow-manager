import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getCrmViewerContext, resolveScopedClientId } from "@/lib/crm/context";

const querySchema = z.object({
  client: z.string().uuid().optional(),
  category: z.string().trim().optional(),
});

export async function GET(req: NextRequest) {
  const url = new URL(req.url);
  const parsed = querySchema.safeParse(Object.fromEntries(url.searchParams));
  if (!parsed.success) {
    return NextResponse.json({ success: false, error: "Invalid query" }, { status: 400 });
  }
  const { client, category } = parsed.data;

  const ctx = await getCrmViewerContext(client);
  if (!ctx) return NextResponse.json({ success: false, error: "Unauthorized" }, { status: 401 });
  const clientId = resolveScopedClientId(ctx);
  if (!clientId) {
    return NextResponse.json(
      { success: false, error: "Admin must pass client" },
      { status: 400 },
    );
  }

  const supabase = await createServerSupabaseClient();
  let query = supabase
    .from("crm_email_templates")
    .select("id, name, category, subject, body, variables, is_default, updated_at")
    .eq("client_id", clientId)
    .order("is_default", { ascending: false })
    .order("name");

  if (category) query = query.eq("category", category);

  const { data, error } = await query;
  if (error) return NextResponse.json({ success: false, error: error.message }, { status: 500 });

  return NextResponse.json({ success: true, data: data ?? [] });
}
