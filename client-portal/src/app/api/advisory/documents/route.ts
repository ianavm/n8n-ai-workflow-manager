import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth";
import { createServiceRoleClient } from "@/lib/supabase/server";

export async function GET(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();
  const { searchParams } = new URL(req.url);
  const clientId = searchParams.get("client_id") ?? "";

  let query = supabase
    .from("fa_documents")
    .select(
      "*, uploaded_by"
    )
    .order("created_at", { ascending: false });

  if (session.role === "client") {
    if (!session.faClientId) {
      return NextResponse.json(
        { error: "No advisory client profile linked" },
        { status: 403 }
      );
    }
    query = query.eq("client_id", session.faClientId);
  } else if (session.firmId) {
    query = query.eq("firm_id", session.firmId);
    if (clientId) {
      query = query.eq("client_id", clientId);
    }
  } else {
    return NextResponse.json(
      { error: "No firm associated with account" },
      { status: 403 }
    );
  }

  const { data, error } = await query;

  if (error) {
    return NextResponse.json(
      { error: "Failed to fetch documents" },
      { status: 500 }
    );
  }

  return NextResponse.json({ success: true, data: data ?? [] });
}

export async function POST(req: NextRequest) {
  const session = await getSession();
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const supabase = await createServiceRoleClient();

  const formData = await req.formData();
  const file = formData.get("file") as File | null;
  const clientId = formData.get("client_id") as string | null;
  const category = (formData.get("category") as string) ?? "other";
  const description = formData.get("description") as string | null;

  if (!file) {
    return NextResponse.json({ error: "File is required" }, { status: 400 });
  }

  // Determine the client ID
  let resolvedClientId: string;
  let firmId: string;

  if (session.role === "client") {
    if (!session.faClientId || !session.firmId) {
      return NextResponse.json(
        { error: "No advisory client profile linked" },
        { status: 403 }
      );
    }
    resolvedClientId = session.faClientId;
    firmId = session.firmId;
  } else {
    if (!clientId) {
      return NextResponse.json(
        { error: "client_id is required for adviser uploads" },
        { status: 400 }
      );
    }
    if (!session.firmId) {
      return NextResponse.json(
        { error: "No firm associated with account" },
        { status: 403 }
      );
    }

    // Verify client belongs to firm
    const { data: client, error: clientError } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("id", clientId)
      .eq("firm_id", session.firmId)
      .single();

    if (clientError || !client) {
      return NextResponse.json(
        { error: "Client not found in your firm" },
        { status: 404 }
      );
    }

    resolvedClientId = clientId;
    firmId = session.firmId;
  }

  // Validate file size (max 25MB)
  const MAX_SIZE = 25 * 1024 * 1024;
  if (file.size > MAX_SIZE) {
    return NextResponse.json(
      { error: "File size exceeds 25MB limit" },
      { status: 400 }
    );
  }

  // Upload to Supabase Storage
  const timestamp = Date.now();
  const safeName = file.name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const storagePath = `${firmId}/${resolvedClientId}/${timestamp}_${safeName}`;

  const arrayBuffer = await file.arrayBuffer();
  const buffer = Buffer.from(arrayBuffer);

  const { error: uploadError } = await supabase.storage
    .from("fa-documents")
    .upload(storagePath, buffer, {
      contentType: file.type,
      upsert: false,
    });

  if (uploadError) {
    return NextResponse.json(
      { error: "Failed to upload file to storage" },
      { status: 500 }
    );
  }

  // Create document record
  const { data, error } = await supabase
    .from("fa_documents")
    .insert({
      firm_id: firmId,
      client_id: resolvedClientId,
      file_name: file.name,
      storage_path: storagePath,
      file_type: file.type,
      file_size: file.size,
      document_type: category,
      description: description ?? null,
      uploaded_by: session.profileId,
      uploaded_by_role: session.role,
    })
    .select()
    .single();

  if (error) {
    // Cleanup storage on DB insert failure
    await supabase.storage.from("fa-documents").remove([storagePath]);
    return NextResponse.json(
      { error: "Failed to create document record" },
      { status: 500 }
    );
  }

  // Audit log
  await supabase.from("fa_audit_log").insert({
    firm_id: firmId,
    performed_by: session.profileId,
    performed_by_type: session.role === "client" ? "client" : "adviser",
    action: "document_uploaded",
    entity_type: "fa_documents",
    entity_id: data.id,
    new_value: {
      file_name: file.name,
      document_type: category,
      client_id: resolvedClientId,
    },
  });

  return NextResponse.json({ success: true, data }, { status: 201 });
}
