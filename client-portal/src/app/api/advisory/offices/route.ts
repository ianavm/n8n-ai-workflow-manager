import { NextResponse } from "next/server";
import { z } from "zod";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const createOfficeSchema = z.object({
  firm_name: z.string().min(2, "Firm name must be at least 2 characters"),
  fsp_number: z.string().optional(),
  contact_email: z.string().email("Invalid contact email"),
  contact_phone: z.string().optional(),
  trading_name: z.string().optional(),
});

export async function GET() {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (session.role !== "super_admin" && session.role !== "owner") {
    return NextResponse.json(
      { error: "Forbidden: Super admin access required" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();

  try {
    const { data, error } = await supabase.rpc("fa_get_all_offices_summary");

    if (error) {
      return NextResponse.json(
        { error: "Failed to fetch offices summary" },
        { status: 500 }
      );
    }

    return NextResponse.json({ success: true, data: data ?? [] });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

export async function POST(request: Request) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  if (session.role !== "super_admin" && session.role !== "owner") {
    return NextResponse.json(
      { error: "Forbidden: Super admin access required" },
      { status: 403 }
    );
  }

  const supabase = await createServiceRoleClient();

  try {
    const body = await request.json();
    const parsed = createOfficeSchema.safeParse(body);

    if (!parsed.success) {
      return NextResponse.json(
        { error: parsed.error.issues[0].message },
        { status: 400 }
      );
    }

    const { firm_name, fsp_number, contact_email, contact_phone, trading_name } =
      parsed.data;

    // Create the firm
    const { data: firm, error: firmError } = await supabase
      .from("fa_firms")
      .insert({
        firm_name,
        fsp_number: fsp_number ?? null,
        contact_email,
        contact_phone: contact_phone ?? null,
        trading_name: trading_name ?? null,
        config: {},
      })
      .select()
      .single();

    if (firmError) {
      if (firmError.code === "23505") {
        return NextResponse.json(
          { error: "A firm with this FSP number already exists" },
          { status: 409 }
        );
      }
      return NextResponse.json(
        { error: "Failed to create office" },
        { status: 500 }
      );
    }

    // Seed default product types for the firm (link from global products)
    // The fa_product_types table is global, so no per-firm seeding needed

    return NextResponse.json({ success: true, data: firm }, { status: 201 });
  } catch {
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
