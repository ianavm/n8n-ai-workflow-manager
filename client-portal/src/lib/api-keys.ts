import { createServiceRoleClient } from "@/lib/supabase/server";
import { NextRequest, NextResponse } from "next/server";

export type ApiKeyValidation =
  | { ok: true; clientId: string }
  | { ok: false; error: string; status: number };

export async function validateApiKey(
  request: NextRequest
): Promise<ApiKeyValidation> {
  const apiKey = request.headers.get("x-api-key");

  if (!apiKey) {
    return { ok: false, error: "Missing X-API-Key header", status: 401 };
  }

  const supabase = await createServiceRoleClient();

  const { data: client, error } = await supabase
    .from("clients")
    .select("id, status")
    .eq("api_key", apiKey)
    .single();

  if (error || !client) {
    return { ok: false, error: "Invalid API key", status: 401 };
  }

  if (client.status !== "active") {
    return { ok: false, error: "Client account is not active", status: 403 };
  }

  return { ok: true, clientId: client.id };
}

export function apiError(message: string, status: number) {
  return NextResponse.json({ error: message }, { status });
}
