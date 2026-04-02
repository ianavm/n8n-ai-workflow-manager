import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

const META_APP_ID = process.env.NEXT_PUBLIC_META_APP_ID || "";
const META_APP_SECRET = process.env.META_APP_SECRET || "";

/**
 * POST /api/portal/whatsapp
 * Exchange Meta Embedded Signup auth code for access token + save connection
 */
export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { code, client_id } = await req.json();

  if (!code || !client_id) {
    return NextResponse.json(
      { error: "Missing code or client_id" },
      { status: 400 }
    );
  }

  // Verify client owns this profile
  if (session.profileId !== client_id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  try {
    // Step 1: Exchange auth code for access token (POST body, not query params)
    const tokenResponse = await fetch(
      `https://graph.facebook.com/v18.0/oauth/access_token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: new URLSearchParams({
          client_id: META_APP_ID,
          client_secret: META_APP_SECRET,
          code,
        }),
      }
    );

    const tokenData = await tokenResponse.json();

    if (!tokenResponse.ok || !tokenData.access_token) {
      return NextResponse.json(
        { error: "Failed to exchange authorization code" },
        { status: 400 }
      );
    }

    const accessToken = tokenData.access_token;

    // Step 2: Get the WABA ID and phone number details
    // The Embedded Signup flow creates a shared WABA under your business
    const debugResponse = await fetch(
      `https://graph.facebook.com/v18.0/debug_token?input_token=${accessToken}`,
      {
        headers: {
          Authorization: `Bearer ${META_APP_ID}|${META_APP_SECRET}`,
        },
      }
    );
    const debugData = await debugResponse.json();

    // Step 3: Get phone numbers from the WABA
    const wabaId =
      debugData.data?.granular_scopes?.find(
        (s: { scope: string; target_ids: string[] }) =>
          s.scope === "whatsapp_business_management"
      )?.target_ids?.[0] || null;

    let phoneNumberId = null;
    let displayPhoneNumber = null;
    let businessName = null;

    if (wabaId) {
      const phoneResponse = await fetch(
        `https://graph.facebook.com/v18.0/${wabaId}/phone_numbers`,
        {
          headers: { Authorization: `Bearer ${accessToken}` },
        }
      );
      const phoneData = await phoneResponse.json();
      const phone = phoneData.data?.[0];

      if (phone) {
        phoneNumberId = phone.id;
        displayPhoneNumber = phone.display_phone_number;
        businessName = phone.verified_name || null;
      }
    }

    // Step 4: Save to Supabase
    const supabase = await createServiceRoleClient();

    const connectionData = {
      client_id,
      waba_id: wabaId,
      phone_number_id: phoneNumberId,
      display_phone_number: displayPhoneNumber,
      business_name: businessName,
      access_token: accessToken, // encrypted at rest by Supabase
      status: phoneNumberId ? "connected" : "pending",
      connected_at: new Date().toISOString(),
      coexistence_enabled: true, // Embedded Signup with WA Business app = coexistence
    };

    // Upsert — create or update
    const { error: dbError } = await supabase
      .from("whatsapp_connections")
      .upsert(connectionData, { onConflict: "client_id" });

    if (dbError) {
      console.error("Failed to save WhatsApp connection:", dbError);
      return NextResponse.json(
        { error: "Failed to save connection" },
        { status: 500 }
      );
    }

    return NextResponse.json({
      success: true,
      status: connectionData.status,
      phone_number: displayPhoneNumber,
    });
  } catch (err) {
    console.error("WhatsApp connection error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}

/**
 * DELETE /api/portal/whatsapp
 * Disconnect WhatsApp for a client
 */
export async function DELETE(req: NextRequest) {
  const session = await getSession();
  if (!session || session.role !== "client") {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { client_id } = await req.json();

  if (session.profileId !== client_id) {
    return NextResponse.json({ error: "Forbidden" }, { status: 403 });
  }

  const supabase = await createServiceRoleClient();

  const { error: dbError } = await supabase
    .from("whatsapp_connections")
    .update({
      status: "not_connected",
      access_token: null,
      phone_number_id: null,
      waba_id: null,
      display_phone_number: null,
      coexistence_enabled: false,
    })
    .eq("client_id", client_id);

  if (dbError) {
    return NextResponse.json(
      { error: "Failed to disconnect" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true });
}
