import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { generatePaymentData, getPayFastUrl } from "@/lib/payfast";

export const dynamic = "force-dynamic";

// GET /api/billing/addons — list available add-ons + client's active ones
export async function GET() {
  try {
    const session = await getSession();
    if (!session) {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();

    // Fetch all active add-ons
    const { data: addons, error: addonsError } = await supabase
      .from("addons")
      .select("*")
      .eq("is_active", true)
      .order("sort_order");

    if (addonsError) {
      console.error("[billing/addons] Error fetching addons:", addonsError);
      return NextResponse.json({ error: "Failed to fetch add-ons" }, { status: 500 });
    }

    // If client, also fetch their active add-ons
    let activeAddonSlugs: string[] = [];

    if (session.role === "client" && session.profileId) {
      const { data: sub } = await supabase
        .from("subscriptions")
        .select("id")
        .eq("client_id", session.profileId)
        .in("status", ["active", "trialing", "past_due"])
        .order("created_at", { ascending: false })
        .limit(1)
        .maybeSingle();

      if (sub) {
        const { data: activeAddons } = await supabase
          .from("subscription_addons")
          .select("addon_id, addons(slug)")
          .eq("subscription_id", sub.id)
          .eq("status", "active");

        if (activeAddons) {
          activeAddonSlugs = activeAddons
            .map((sa: Record<string, unknown>) => {
              const addon = sa.addons as Record<string, unknown> | null;
              return addon?.slug as string;
            })
            .filter(Boolean);
        }
      }
    }

    return NextResponse.json({
      addons: addons ?? [],
      activeAddonSlugs,
    });
  } catch (error) {
    console.error("[billing/addons] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}

// POST /api/billing/addons — purchase or cancel an add-on
export async function POST(request: NextRequest) {
  try {
    const session = await getSession();
    if (!session || session.role !== "client") {
      return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
    }

    const body = await request.json();
    const { addonSlug, action } = body;

    if (!addonSlug || !action) {
      return NextResponse.json(
        { error: "addonSlug and action are required" },
        { status: 400 }
      );
    }

    if (action !== "purchase" && action !== "cancel") {
      return NextResponse.json(
        { error: "action must be 'purchase' or 'cancel'" },
        { status: 400 }
      );
    }

    const supabase = await createServiceRoleClient();
    const clientId = session.profileId;

    // Get current subscription
    const { data: sub, error: subError } = await supabase
      .from("subscriptions")
      .select("id, status")
      .eq("client_id", clientId)
      .in("status", ["active", "trialing", "past_due"])
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle();

    if (subError || !sub) {
      return NextResponse.json(
        { error: "No active subscription found. Please subscribe to a plan first." },
        { status: 400 }
      );
    }

    // Get add-on
    const { data: addon, error: addonError } = await supabase
      .from("addons")
      .select("*")
      .eq("slug", addonSlug)
      .eq("is_active", true)
      .single();

    if (addonError || !addon) {
      return NextResponse.json(
        { error: "Add-on not found" },
        { status: 404 }
      );
    }

    if (action === "purchase") {
      // Check if already active
      const { data: existing } = await supabase
        .from("subscription_addons")
        .select("id")
        .eq("subscription_id", sub.id)
        .eq("addon_id", addon.id)
        .eq("status", "active")
        .maybeSingle();

      if (existing) {
        return NextResponse.json(
          { error: "This add-on is already active on your subscription" },
          { status: 409 }
        );
      }

      // Get client details for checkout
      const { data: client } = await supabase
        .from("clients")
        .select("id, email, full_name")
        .eq("id", clientId)
        .single();

      if (!client) {
        return NextResponse.json({ error: "Client not found" }, { status: 404 });
      }

      const baseUrl =
        process.env.NEXT_PUBLIC_APP_URL || "https://portal.anyvisionmedia.com";

      // PayFast checkout for add-on purchase
      const paymentData = generatePaymentData({
        clientId: client.id,
        clientEmail: client.email,
        clientName: client.full_name,
        planName: addon.name,
        amount: addon.price_monthly,
        billingInterval: "monthly",
        returnUrl: `${baseUrl}/portal/billing?addon=success`,
        cancelUrl: `${baseUrl}/portal/billing?addon=cancelled`,
        notifyUrl: `${baseUrl}/api/webhooks/payfast`,
      });

      // Attach custom fields for webhook identification
      const paymentDataWithCustom: Record<string, string> = {
        ...paymentData,
        custom_str1: client.id,
        custom_str2: addon.id,
        custom_str3: "addon",
      };

      // Log activity
      await supabase.from("activity_log").insert({
        actor_type: "client",
        actor_id: clientId,
        action: "addon_checkout_started",
        target_type: "addon",
        target_id: addon.id,
        details: {
          addon_name: addon.name,
          addon_slug: addon.slug,
          price_monthly: addon.price_monthly,
        },
      });

      return NextResponse.json({
        paymentUrl: getPayFastUrl(),
        paymentData: paymentDataWithCustom,
      });
    }

    if (action === "cancel") {
      // Find active subscription_addon
      const { data: activeAddon, error: findError } = await supabase
        .from("subscription_addons")
        .select("id")
        .eq("subscription_id", sub.id)
        .eq("addon_id", addon.id)
        .eq("status", "active")
        .maybeSingle();

      if (findError || !activeAddon) {
        return NextResponse.json(
          { error: "This add-on is not active on your subscription" },
          { status: 404 }
        );
      }

      // Deactivate
      const { error: updateError } = await supabase
        .from("subscription_addons")
        .update({
          status: "canceled",
          deactivated_at: new Date().toISOString(),
        })
        .eq("id", activeAddon.id);

      if (updateError) {
        console.error("[billing/addons] Cancel error:", updateError);
        return NextResponse.json(
          { error: "Failed to cancel add-on" },
          { status: 500 }
        );
      }

      // Log activity
      await supabase.from("activity_log").insert({
        actor_type: "client",
        actor_id: clientId,
        action: "addon_canceled",
        target_type: "addon",
        target_id: addon.id,
        details: {
          addon_name: addon.name,
          addon_slug: addon.slug,
        },
      });

      return NextResponse.json({
        message: `${addon.name} canceled successfully`,
      });
    }
  } catch (error) {
    console.error("[billing/addons] Error:", error);
    return NextResponse.json({ error: "Internal server error" }, { status: 500 });
  }
}
