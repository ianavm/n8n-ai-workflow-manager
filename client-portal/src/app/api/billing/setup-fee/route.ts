import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

// Valid service types and their default prices (cents)
const SERVICE_TYPES: Record<string, { name: string; defaultPrice: number }> = {
  guided_onboarding: { name: "Guided Onboarding (1h call)", defaultPrice: 299900 },
  department_setup: { name: "Department Setup", defaultPrice: 499900 },
  custom_workflow: { name: "Custom Workflow Build", defaultPrice: 750000 },
  data_migration: { name: "Data Migration", defaultPrice: 999900 },
  custom_integration: { name: "Custom Integration Build", defaultPrice: 1499900 },
  full_setup: { name: "Full Platform Setup", defaultPrice: 4999900 },
};

// GET /api/billing/setup-fee — list available setup services + client's fees
export async function GET() {
  try {
    const session = await getSession();
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const services = Object.entries(SERVICE_TYPES).map(([type, info]) => ({
      type,
      name: info.name,
      price: info.defaultPrice,
    }));

    // If client, fetch their setup fees
    let clientFees: Record<string, unknown>[] = [];

    if (session.role === "client" && session.profileId) {
      const supabase = await createServiceRoleClient();
      const { data } = await supabase
        .from("setup_fees")
        .select("*")
        .eq("client_id", session.profileId)
        .order("created_at", { ascending: false });

      clientFees = data ?? [];
    }

    return NextResponse.json({ services, clientFees });
  } catch (error) {
    console.error("[billing/setup-fee] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

// POST /api/billing/setup-fee — create a setup fee record (admin only for now)
export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session || session.role !== "superior_admin") {
      return NextResponse.json({ error: "Superior admin access required" }, { status: 403 });
    }

    const body = await request.json();
    const { clientId, serviceType, amountCents, description, status } = body;

    if (!clientId || !serviceType) {
      return NextResponse.json(
        { error: "clientId and serviceType are required" },
        { status: 400 }
      );
    }

    const serviceInfo = SERVICE_TYPES[serviceType];
    if (!serviceInfo) {
      return NextResponse.json(
        { error: `Invalid serviceType. Valid types: ${Object.keys(SERVICE_TYPES).join(", ")}` },
        { status: 400 }
      );
    }

    const finalAmount = amountCents ?? serviceInfo.defaultPrice;
    const finalStatus = status ?? "pending";

    if (!["pending", "paid", "waived", "refunded"].includes(finalStatus)) {
      return NextResponse.json(
        { error: "status must be pending, paid, waived, or refunded" },
        { status: 400 }
      );
    }

    const supabase = await createServiceRoleClient();

    const { data: fee, error: insertError } = await supabase
      .from("setup_fees")
      .insert({
        client_id: clientId,
        service_type: serviceType,
        description: description || serviceInfo.name,
        amount_cents: finalAmount,
        status: finalStatus,
        paid_at: finalStatus === "paid" || finalStatus === "waived"
          ? new Date().toISOString()
          : null,
      })
      .select()
      .single();

    if (insertError) {
      console.error("[billing/setup-fee] Insert error:", insertError);
      return NextResponse.json({ error: "Failed to create setup fee" }, { status: 500 });
    }

    // Log activity
    await supabase.from("activity_log").insert({
      actor_type: "admin",
      actor_id: session.profileId,
      action: "setup_fee_created",
      target_type: "setup_fee",
      target_id: fee.id,
      details: {
        client_id: clientId,
        service_type: serviceType,
        amount_cents: finalAmount,
        status: finalStatus,
      },
    });

    return NextResponse.json({ fee });
  } catch (error) {
    console.error("[billing/setup-fee] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
