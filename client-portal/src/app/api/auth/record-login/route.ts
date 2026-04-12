import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { extractClientIp } from "@/lib/validation";

export async function POST(request: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const ip = extractClientIp(request);
  const userAgent = request.headers.get("user-agent") || "Unknown";
  const device = parseDevice(userAgent);

  const svc = await createServiceRoleClient();
  const now = new Date().toISOString();

  const table = session.role === "client" ? "clients" : "admin_users";

  await svc
    .from(table)
    .update({
      last_login_at: now,
      last_login_ip: ip,
      last_login_device: device,
    })
    .eq("id", session.profileId);

  return NextResponse.json({ success: true });
}

function parseDevice(ua: string): string {
  const parts: string[] = [];

  if (/Chrome\//.test(ua) && !/Edg\//.test(ua)) parts.push("Chrome");
  else if (/Edg\//.test(ua)) parts.push("Edge");
  else if (/Firefox\//.test(ua)) parts.push("Firefox");
  else if (/Safari\//.test(ua) && !/Chrome\//.test(ua)) parts.push("Safari");
  else parts.push("Browser");

  if (/Windows/.test(ua)) parts.push("on Windows");
  else if (/Mac OS/.test(ua)) parts.push("on macOS");
  else if (/Linux/.test(ua)) parts.push("on Linux");
  else if (/Android/.test(ua)) parts.push("on Android");
  else if (/iPhone|iPad/.test(ua)) parts.push("on iOS");

  return parts.join(" ");
}
