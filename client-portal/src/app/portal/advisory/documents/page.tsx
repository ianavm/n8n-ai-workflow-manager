"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Download, File, FolderOpen, Upload } from "lucide-react";

import { createClient } from "@/lib/supabase/client";
import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";
import { LoadingState } from "@/components/portal/LoadingState";
import { ErrorState } from "@/components/portal/ErrorState";
import { Button } from "@/components/ui-shadcn/button";
import { Card } from "@/components/ui-shadcn/card";

interface FaDocument {
  id: string;
  file_name: string;
  document_type: string;
  storage_url: string | null;
  file_size: number | null;
  created_at: string;
}

const TYPE_COLOR: Record<string, string> = {
  identity: "var(--accent-teal)",
  financial: "var(--accent-teal)",
  insurance: "var(--warning)",
  tax: "var(--danger)",
  compliance: "var(--accent-purple)",
  other: "var(--text-dim)",
};

function formatFileSize(bytes: number | null): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function groupByType(docs: FaDocument[]): Record<string, FaDocument[]> {
  const groups: Record<string, FaDocument[]> = {};
  for (const doc of docs) {
    const type = doc.document_type || "other";
    groups[type] = [...(groups[type] ?? []), doc];
  }
  return groups;
}

export default function AdvisoryDocuments() {
  const supabase = createClient();
  const [documents, setDocuments] = useState<FaDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: portalClient } = await supabase
      .from("clients")
      .select("id")
      .eq("auth_user_id", userData.user.id)
      .single();
    if (!portalClient) {
      setError("No portal account found");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id, firm_id")
      .eq("portal_client_id", portalClient.id)
      .single();
    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: docData, error: docErr } = await supabase
      .from("fa_documents")
      .select("id, file_name, document_type, storage_url, file_size, created_at")
      .eq("client_id", client.id)
      .order("created_at", { ascending: false });

    if (docErr) {
      setError(docErr.message);
      setLoading(false);
      return;
    }

    setDocuments(docData || []);
    setLoading(false);
  }, [supabase]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    setUploading(true);
    setUploadMsg(null);

    const formData = new FormData();
    for (let i = 0; i < files.length; i++) {
      formData.append("file", files[i]);
    }

    try {
      const res = await fetch("/api/advisory/documents", { method: "POST", body: formData });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setUploadMsg({ type: "error", text: body.error || "Upload failed." });
      } else {
        setUploadMsg({ type: "success", text: "Documents uploaded successfully." });
        fetchDocuments();
        setTimeout(() => setUploadMsg(null), 3000);
      }
    } catch {
      setUploadMsg({ type: "error", text: "Upload failed. Please try again." });
    }

    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  if (loading) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Documents" description="Your FICA documents, policies, and financial records." />
        <LoadingState variant="list" rows={4} />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col gap-6">
        <PageHeader eyebrow="Advisory" title="Documents" description="Your FICA documents, policies, and financial records." />
        <ErrorState title="Unable to load documents" description={error} onRetry={fetchDocuments} />
      </div>
    );
  }

  const grouped = groupByType(documents);

  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Advisory"
        title="Documents"
        description="Your FICA documents, policies, and financial records."
        actions={
          <>
            {uploadMsg ? (
              <span
                className="text-sm font-medium"
                style={{
                  color:
                    uploadMsg.type === "error" ? "var(--danger)" : "var(--accent-teal)",
                }}
              >
                {uploadMsg.text}
              </span>
            ) : null}
            <label>
              <Button
                variant="default"
                size="md"
                loading={uploading}
                disabled={uploading}
                asChild
              >
                <span className="cursor-pointer">
                  <Upload className="size-4" />
                  {uploading ? "Uploading…" : "Upload"}
                </span>
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
            </label>
          </>
        }
      />

      {documents.length === 0 ? (
        <EmptyState icon={<FolderOpen className="size-5" />} title="No documents yet" description="Upload FICA documents, insurance policies, or tax records to keep them at your fingertips." />
      ) : (
        <div className="flex flex-col gap-6">
          {Object.entries(grouped).map(([type, docs]) => {
            const color = TYPE_COLOR[type.toLowerCase()] || TYPE_COLOR.other;
            return (
              <section key={type}>
                <div className="flex items-center gap-2 mb-3">
                  <span aria-hidden className="size-2 rounded-full shrink-0" style={{ background: color }} />
                  <h3 className="text-sm font-semibold text-[var(--text-muted)] capitalize">
                    {type.replace(/_/g, " ")}
                  </h3>
                  <span className="text-xs text-[var(--text-dim)]">({docs.length})</span>
                </div>
                <ul className="flex flex-col gap-2">
                  {docs.map((doc) => (
                    <li key={doc.id}>
                      <Card variant="default" padding="md">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <File className="size-4 shrink-0" style={{ color }} aria-hidden />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-foreground truncate">{doc.file_name}</p>
                              <p className="text-xs text-[var(--text-dim)] mt-0.5">
                                {new Date(doc.created_at).toLocaleDateString("en-ZA")}
                                {doc.file_size != null ? ` · ${formatFileSize(doc.file_size)}` : ""}
                              </p>
                            </div>
                          </div>
                          {doc.storage_url ? (
                            <Button asChild variant="outline" size="sm">
                              <a href={doc.storage_url} target="_blank" rel="noopener noreferrer">
                                <Download className="size-3.5" />
                                Download
                              </a>
                            </Button>
                          ) : null}
                        </div>
                      </Card>
                    </li>
                  ))}
                </ul>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}
