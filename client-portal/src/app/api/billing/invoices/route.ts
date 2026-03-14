import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// GET /api/billing/invoices — list invoices for authenticated client
export async function GET(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Parse pagination params
    const { searchParams } = new URL(request.url);
    const page = Math.max(1, parseInt(searchParams.get("page") || "1", 10));
    const limit = Math.min(50, Math.max(1, parseInt(searchParams.get("limit") || "10", 10)));
    const offset = (page - 1) * limit;

    // Get total count
    const { count, error: countError } = await supabase
      .from("invoices")
      .select("*", { count: "exact", head: true })
      .eq("client_id", clientId);

    if (countError) {
      console.error("[billing/invoices] Count error:", countError);
      return NextResponse.json(
        { error: "Failed to fetch invoices" },
        { status: 500 }
      );
    }

    // Get paginated invoices with subscription plan name
    const { data: invoices, error: fetchError } = await supabase
      .from("invoices")
      .select("*, subscriptions(billing_interval, plans(name, slug))")
      .eq("client_id", clientId)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (fetchError) {
      console.error("[billing/invoices] Fetch error:", fetchError);
      return NextResponse.json(
        { error: "Failed to fetch invoices" },
        { status: 500 }
      );
    }

    const totalPages = Math.ceil((count || 0) / limit);

    return NextResponse.json({
      invoices: invoices || [],
      pagination: {
        page,
        limit,
        total: count || 0,
        totalPages,
        hasMore: page < totalPages,
      },
    });
  } catch (error) {
    console.error("[billing/invoices] Error:", error);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
