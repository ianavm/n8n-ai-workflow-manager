import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

interface OpenRouterMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

interface OpenRouterChoice {
  message: { content: string };
}

interface OpenRouterResponse {
  choices: OpenRouterChoice[];
}

export async function POST(
  _req: NextRequest,
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

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "AI suggestions are not configured. OPENROUTER_API_KEY is missing." },
      { status: 503 }
    );
  }

  const { id } = await params;
  const supabase = await createServiceRoleClient();

  // Verify ownership
  const { data: conv } = await supabase
    .from("mkt_conversations")
    .select("id, channel, subject")
    .eq("id", id)
    .eq("client_id", clientId)
    .single();

  if (!conv) {
    return NextResponse.json({ error: "Conversation not found" }, { status: 404 });
  }

  // Fetch last 10 messages for context
  const { data: recentMessages } = await supabase
    .from("mkt_messages")
    .select("direction, content, created_at")
    .eq("conversation_id", id)
    .order("created_at", { ascending: false })
    .limit(10);

  // Build prompt context from messages (reverse to chronological order)
  const messageContext = (recentMessages ?? [])
    .reverse()
    .map((m) => {
      const role = m.direction === "inbound" ? "Customer" : "Us";
      return `${role}: ${m.content}`;
    })
    .join("\n");

  const messages: OpenRouterMessage[] = [
    {
      role: "system",
      content:
        "You are a helpful marketing assistant. Generate a professional, friendly response to the customer's message. Keep it concise and actionable. Do not include any greeting prefixes like 'Hi' or 'Hello' unless it fits naturally.",
    },
    {
      role: "user",
      content: `Channel: ${conv.channel ?? "unknown"}\nSubject: ${conv.subject ?? "N/A"}\n\nConversation:\n${messageContext}\n\nGenerate a professional reply to the customer's last message.`,
    },
  ];

  try {
    const response = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "HTTP-Referer": "https://portal.anyvisionmedia.com",
        "X-Title": "AVM Client Portal",
      },
      body: JSON.stringify({
        model: "anthropic/claude-sonnet-4-20250514",
        messages,
        max_tokens: 500,
        temperature: 0.7,
      }),
    });

    if (!response.ok) {
      const errorBody = await response.text();
      return NextResponse.json(
        { error: `AI service error: ${response.status}`, detail: errorBody },
        { status: 502 }
      );
    }

    const result = (await response.json()) as OpenRouterResponse;
    const suggestion = result.choices?.[0]?.message?.content ?? "";

    return NextResponse.json({ suggestion });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "AI request failed";
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
