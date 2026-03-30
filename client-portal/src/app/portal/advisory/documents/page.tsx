"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { createClient } from "@/lib/supabase/client";
import {
  FileText,
  Upload,
  Download,
  File,
  FolderOpen,
} from "lucide-react";

interface FaDocument {
  id: string;
  document_name: string;
  document_type: string;
  file_url: string | null;
  file_size: number | null;
  uploaded_at: string;
  status: string | null;
}

const glassCard: React.CSSProperties = {
  background: "rgba(255,255,255,0.03)",
  borderRadius: "16px",
  border: "1px solid rgba(255,255,255,0.06)",
  backdropFilter: "blur(20px)",
  WebkitBackdropFilter: "blur(20px)",
  padding: "24px",
};

const typeColors: Record<string, string> = {
  identity: "#6C63FF",
  financial: "#00D4AA",
  insurance: "#F59E0B",
  tax: "#EF4444",
  compliance: "#8B5CF6",
  other: "#6B7280",
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
    if (!groups[type]) {
      groups[type] = [];
    }
    groups[type] = [...groups[type], doc];
  }
  return groups;
}

export default function AdvisoryDocuments() {
  const supabase = createClient();
  const [documents, setDocuments] = useState<FaDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    const { data: userData } = await supabase.auth.getUser();
    if (!userData.user) {
      setError("Not authenticated");
      setLoading(false);
      return;
    }

    const { data: client } = await supabase
      .from("fa_clients")
      .select("id")
      .eq("portal_client_id", userData.user.id)
      .single();

    if (!client) {
      setError("No advisory profile found.");
      setLoading(false);
      return;
    }

    const { data: docData, error: docErr } = await supabase
      .from("fa_documents")
      .select("id, document_name, document_type, file_url, file_size, uploaded_at, status")
      .eq("client_id", client.id)
      .order("uploaded_at", { ascending: false });

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
      formData.append("files", files[i]);
    }

    try {
      const res = await fetch("/api/advisory/documents", {
        method: "POST",
        body: formData,
      });

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        setUploadMsg(body.error || "Upload failed.");
      } else {
        setUploadMsg("Documents uploaded successfully.");
        fetchDocuments();
        setTimeout(() => setUploadMsg(null), 3000);
      }
    } catch {
      setUploadMsg("Upload failed. Please try again.");
    }

    setUploading(false);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "40vh" }}>
        <div
          style={{
            width: "32px",
            height: "32px",
            border: "2px solid #6C63FF",
            borderTopColor: "transparent",
            borderRadius: "50%",
            animation: "spin 0.8s linear infinite",
          }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ ...glassCard, textAlign: "center", color: "#EF4444", marginTop: "24px" }}>
        <p style={{ fontSize: "14px" }}>{error}</p>
      </div>
    );
  }

  const grouped = groupByType(documents);

  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "24px" }}>
        <div>
          <h1 style={{ fontSize: "24px", fontWeight: 600, color: "#fff" }}>Documents</h1>
          <p style={{ fontSize: "14px", color: "#6B7280", marginTop: "4px" }}>
            Your FICA documents, policies, and financial records.
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          {uploadMsg && (
            <span style={{ fontSize: "13px", color: uploadMsg.includes("failed") ? "#EF4444" : "#10B981" }}>
              {uploadMsg}
            </span>
          )}
          <label
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "10px 18px",
              borderRadius: "10px",
              background: "linear-gradient(135deg, #6C63FF, #5B5FC7)",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 600,
              cursor: uploading ? "not-allowed" : "pointer",
              opacity: uploading ? 0.6 : 1,
            }}
          >
            <Upload size={16} />
            {uploading ? "Uploading..." : "Upload"}
            <input
              ref={fileInputRef}
              type="file"
              multiple
              onChange={handleUpload}
              style={{ display: "none" }}
              disabled={uploading}
            />
          </label>
        </div>
      </div>

      {documents.length === 0 ? (
        <div style={{ ...glassCard, textAlign: "center" }}>
          <FolderOpen size={32} style={{ color: "#6B7280", margin: "0 auto 12px" }} />
          <p style={{ fontSize: "14px", color: "#6B7280" }}>No documents yet.</p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
          {Object.entries(grouped).map(([type, docs]) => (
            <div key={type}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "12px" }}>
                <div
                  style={{
                    width: "8px",
                    height: "8px",
                    borderRadius: "50%",
                    background: typeColors[type.toLowerCase()] || typeColors.other,
                  }}
                />
                <h3 style={{ fontSize: "14px", fontWeight: 600, color: "#B0B8C8", textTransform: "capitalize" }}>
                  {type.replace(/_/g, " ")}
                </h3>
                <span style={{ fontSize: "12px", color: "#6B7280" }}>({docs.length})</span>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                {docs.map((doc) => (
                  <div
                    key={doc.id}
                    style={{
                      ...glassCard,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      padding: "14px 18px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <File size={18} style={{ color: typeColors[type.toLowerCase()] || typeColors.other, flexShrink: 0 }} />
                      <div>
                        <div style={{ fontSize: "14px", fontWeight: 500, color: "#fff" }}>
                          {doc.document_name}
                        </div>
                        <div style={{ fontSize: "12px", color: "#6B7280", marginTop: "2px" }}>
                          {new Date(doc.uploaded_at).toLocaleDateString("en-ZA")}
                          {doc.file_size != null && ` - ${formatFileSize(doc.file_size)}`}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      {doc.status && (
                        <span
                          style={{
                            fontSize: "11px",
                            fontWeight: 600,
                            padding: "3px 8px",
                            borderRadius: "4px",
                            background: doc.status === "verified"
                              ? "rgba(16,185,129,0.1)"
                              : "rgba(245,158,11,0.1)",
                            color: doc.status === "verified" ? "#10B981" : "#F59E0B",
                            textTransform: "capitalize",
                          }}
                        >
                          {doc.status}
                        </span>
                      )}
                      {doc.file_url && (
                        <a
                          href={doc.file_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{
                            display: "inline-flex",
                            alignItems: "center",
                            gap: "4px",
                            padding: "6px 10px",
                            borderRadius: "6px",
                            background: "rgba(255,255,255,0.05)",
                            color: "#B0B8C8",
                            fontSize: "12px",
                            textDecoration: "none",
                            border: "1px solid rgba(255,255,255,0.08)",
                          }}
                        >
                          <Download size={12} />
                          Download
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
