import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";
import { z } from "zod";

const createMessageSchema = z.object({
  content: z.string().min(1).max(10000),
  content_type: z.enum(["text", "image", "file", "link"]).default("text"),
});

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { id } = await params;
  const supabase = await createServiceRoleClient();

  // Verify the conversation belongs to this client
  const { data: conv } = await supabase
    .from("mkt_conversations")
    .select("id")
    .eq("id", id)
    .eq("client_id", clientId)
    .single();

  if (!conv) {
    return NextResponse.json({ error: "Conversation not found" }, { status: 404 });
  }

  const url = new URL(req.url);
  const before = url.searchParams.get("before");
  const page = Math.max(1, parseInt(url.searchParams.get("page") ?? "1", 10));
  const limit = Math.min(100, Math.max(1, parseInt(url.searchParams.get("limit") ?? "50", 10)));
  const offset = (page - 1) * limit;

  let query = supabase
    .from("mkt_messages")
    .select("*", { count: "exact" })
    .eq("conversation_id", id)
    .order("created_at", { ascending: true });

  if (before) {
    query = query.lt("created_at", before);
  }

  query = query.range(offset, offset + limit - 1);

  const { data, error, count } = await query;

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json({
    data: data ?? [],
    meta: { total: count ?? 0, page, limit },
  });
}

export async function POST(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const clientId = session.role === "client" ? session.profileId : null;
  if (!clientId) {
    return NextResponse.json({ error: "Client access required" }, { status: 403 });
  }

  const { id } = await params;
  const body = await req.json();
  const parsed = createMessageSchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: "Invalid payload", details: parsed.error.flatten() },
      { status: 400 }
    );
  }

  const supabase = await createServiceRoleClient();

  // Verify the conversation belongs to this client
  const { data: conv } = await supabase
    .from("mkt_conversations")
    .select("id")
    .eq("id", id)
    .eq("client_id", clientId)
    .single();

  if (!conv) {
    return NextResponse.json({ error: "Conversation not found" }, { status: 404 });
  }

  // Insert the message
  const { data: message, error: msgError } = await supabase
    .from("mkt_messages")
    .insert({
      conversation_id: id,
      client_id: clientId,
      direction: "outbound",
      content: parsed.data.content,
      content_type: parsed.data.content_type,
    })
    .select()
    .single();

  if (msgError) {
    return NextResponse.json({ error: msgError.message }, { status: 500 });
  }

  // Update conversation: last_message_at and status
  await supabase
    .from("mkt_conversations")
    .update({
      last_message_at: new Date().toISOString(),
      status: "replied",
      updated_at: new Date().toISOString(),
    })
    .eq("id", id)
    .eq("client_id", clientId);

  return NextResponse.json({ data: message }, { status: 201 });
}
