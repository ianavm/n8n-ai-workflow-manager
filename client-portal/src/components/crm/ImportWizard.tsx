"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { CheckCircle2, FileText, Loader2, Upload, XCircle } from "lucide-react";
import { CardShell } from "./CardShell";
import { FIELD_DEFINITIONS, type CrmTargetField } from "@/lib/crm/csv-mapping";

type Step = "upload" | "mapping" | "ingesting" | "done" | "error";

interface UploadResponse {
  success: boolean;
  data?: {
    importId: string;
    headers: string[];
    mapping: Record<string, CrmTargetField | null>;
    preview: Record<string, string>[];
    rowsTotal: number;
  };
  error?: string;
}

interface IngestResponse {
  success: boolean;
  data?: { ingested: number; failed: number; errors: Array<{ row: number; reason: string }> };
  error?: string;
}

export function ImportWizard() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("upload");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // After upload
  const [importId, setImportId] = useState<string | null>(null);
  const [headers, setHeaders] = useState<string[]>([]);
  const [mapping, setMapping] = useState<Record<string, CrmTargetField | null>>({});
  const [preview, setPreview] = useState<Record<string, string>[]>([]);
  const [rowsTotal, setRowsTotal] = useState(0);

  // After ingest
  const [ingestResult, setIngestResult] = useState<IngestResponse["data"] | null>(null);

  const mappedCount = useMemo(
    () => Object.values(mapping).filter(Boolean).length,
    [mapping],
  );

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setErrorMessage(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const resp = await fetch("/api/crm/imports", { method: "POST", body: form });
      const json = (await resp.json()) as UploadResponse;
      if (!resp.ok || !json.success || !json.data) {
        throw new Error(json.error ?? "Upload failed");
      }
      setImportId(json.data.importId);
      setHeaders(json.data.headers);
      setMapping(json.data.mapping);
      setPreview(json.data.preview);
      setRowsTotal(json.data.rowsTotal);
      setStep("mapping");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Upload failed");
      setStep("error");
    } finally {
      setUploading(false);
    }
  }

  async function handleIngest() {
    if (!importId) return;
    setStep("ingesting");
    setErrorMessage(null);
    try {
      const resp = await fetch(`/api/crm/imports/${importId}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ mapping, defaultStageKey: "new" }),
      });
      const json = (await resp.json()) as IngestResponse;
      if (!resp.ok || !json.success || !json.data) {
        throw new Error(json.error ?? "Ingest failed");
      }
      setIngestResult(json.data);
      setStep("done");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Ingest failed");
      setStep("error");
    }
  }

  function resetWizard() {
    setStep("upload");
    setFile(null);
    setImportId(null);
    setHeaders([]);
    setMapping({});
    setPreview([]);
    setRowsTotal(0);
    setIngestResult(null);
    setErrorMessage(null);
  }

  return (
    <div className="space-y-5">
      <Stepper step={step} />

      {step === "upload" && (
        <UploadStep
          file={file}
          setFile={setFile}
          uploading={uploading}
          onUpload={handleUpload}
        />
      )}

      {step === "mapping" && (
        <MappingStep
          headers={headers}
          mapping={mapping}
          setMapping={setMapping}
          preview={preview}
          rowsTotal={rowsTotal}
          mappedCount={mappedCount}
          onIngest={handleIngest}
          onReset={resetWizard}
        />
      )}

      {step === "ingesting" && (
        <CardShell>
          <div className="flex items-center gap-3 py-6 text-[#B0B8C8]">
            <Loader2 size={18} className="animate-spin text-[#FF6D5A]" />
            <span>Ingesting {rowsTotal.toLocaleString()} rows… this takes a few seconds per thousand rows.</span>
          </div>
        </CardShell>
      )}

      {step === "done" && ingestResult && (
        <DoneStep
          ingested={ingestResult.ingested}
          failed={ingestResult.failed}
          errors={ingestResult.errors}
          onAnother={resetWizard}
          onViewLeads={() => router.push("/portal/crm/leads")}
        />
      )}

      {step === "error" && (
        <CardShell>
          <div className="flex items-start gap-3 py-2">
            <XCircle size={20} className="text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-white">Something went wrong</p>
              <p className="mt-1 text-sm text-[#B0B8C8]">{errorMessage}</p>
              <button
                type="button"
                onClick={resetWizard}
                className="mt-3 px-3 py-1.5 text-xs rounded-md bg-[rgba(255,255,255,0.05)] text-white hover:bg-[rgba(255,255,255,0.08)]"
              >
                Start over
              </button>
            </div>
          </div>
        </CardShell>
      )}
    </div>
  );
}

function Stepper({ step }: { step: Step }) {
  const steps: { key: Step | "done"; label: string }[] = [
    { key: "upload", label: "Upload" },
    { key: "mapping", label: "Map fields" },
    { key: "done", label: "Done" },
  ];
  const currentIdx =
    step === "upload" ? 0 : step === "mapping" || step === "ingesting" ? 1 : 2;

  return (
    <ol className="flex items-center gap-3 text-xs">
      {steps.map((s, i) => {
        const active = i === currentIdx;
        const done = i < currentIdx;
        return (
          <li key={s.key} className="flex items-center gap-2">
            <span
              className={`w-6 h-6 rounded-full grid place-items-center text-[11px] font-semibold ${
                active
                  ? "bg-[rgba(255,109,90,0.2)] text-[#FF6D5A] border border-[rgba(255,109,90,0.45)]"
                  : done
                    ? "bg-[rgba(16,185,129,0.15)] text-[#10B981] border border-[rgba(16,185,129,0.35)]"
                    : "bg-[rgba(255,255,255,0.04)] text-[#71717A] border border-[rgba(255,255,255,0.08)]"
              }`}
            >
              {done ? "✓" : i + 1}
            </span>
            <span className={active ? "text-white font-medium" : "text-[#71717A]"}>{s.label}</span>
            {i < steps.length - 1 && <span className="w-8 h-px bg-[rgba(255,255,255,0.08)]" />}
          </li>
        );
      })}
    </ol>
  );
}

function UploadStep({
  file,
  setFile,
  uploading,
  onUpload,
}: {
  file: File | null;
  setFile: (f: File | null) => void;
  uploading: boolean;
  onUpload: () => void;
}) {
  return (
    <CardShell title="1. Choose CSV">
      <div className="space-y-4">
        <label
          htmlFor="csv-file"
          className="block rounded-xl border border-dashed border-[rgba(255,255,255,0.12)] bg-[rgba(255,255,255,0.02)] hover:border-[rgba(255,109,90,0.4)] hover:bg-[rgba(255,109,90,0.04)] transition-colors cursor-pointer py-10 px-6 text-center"
        >
          <Upload size={22} className="mx-auto text-[#FF6D5A]" />
          <div className="mt-3 text-sm font-medium text-white">
            {file ? file.name : "Click to choose a CSV file"}
          </div>
          <div className="mt-1 text-xs text-[#71717A]">
            Up to 10 MB · Up to 10 000 rows · UTF-8 recommended
          </div>
          <input
            id="csv-file"
            type="file"
            accept=".csv,text/csv,application/vnd.ms-excel"
            className="sr-only"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
        </label>

        {file && (
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg bg-[rgba(255,255,255,0.02)] border border-[rgba(255,255,255,0.06)]">
            <FileText size={16} className="text-[#B0B8C8]" />
            <div className="flex-1 min-w-0">
              <div className="text-sm text-white truncate">{file.name}</div>
              <div className="text-xs text-[#71717A]">{(file.size / 1024).toFixed(1)} KB</div>
            </div>
            <button
              type="button"
              onClick={() => setFile(null)}
              className="text-xs text-[#B0B8C8] hover:text-white"
            >
              Remove
            </button>
          </div>
        )}

        <div className="flex items-center gap-3">
          <button
            type="button"
            disabled={!file || uploading}
            onClick={onUpload}
            className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              !file || uploading
                ? "border border-[rgba(255,255,255,0.06)] text-[#71717A] opacity-50 cursor-not-allowed"
                : "border border-[rgba(255,109,90,0.35)] bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.22)]"
            }`}
          >
            {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
            {uploading ? "Uploading…" : "Upload and preview"}
          </button>
          <span className="text-xs text-[#71717A]">We&apos;ll detect column names automatically.</span>
        </div>
      </div>
    </CardShell>
  );
}

function MappingStep({
  headers,
  mapping,
  setMapping,
  preview,
  rowsTotal,
  mappedCount,
  onIngest,
  onReset,
}: {
  headers: string[];
  mapping: Record<string, CrmTargetField | null>;
  setMapping: (m: Record<string, CrmTargetField | null>) => void;
  preview: Record<string, string>[];
  rowsTotal: number;
  mappedCount: number;
  onIngest: () => void;
  onReset: () => void;
}) {
  // Group fields in the dropdown by group for readability
  const groups: Array<{ label: string; fields: typeof FIELD_DEFINITIONS }> = [
    { label: "Company", fields: FIELD_DEFINITIONS.filter((f) => f.group === "company") },
    { label: "Contact", fields: FIELD_DEFINITIONS.filter((f) => f.group === "contact") },
    { label: "Lead", fields: FIELD_DEFINITIONS.filter((f) => f.group === "lead") },
  ];

  const usedTargets = new Set(Object.values(mapping).filter(Boolean) as CrmTargetField[]);

  function setCol(col: string, target: CrmTargetField | null) {
    const next = { ...mapping, [col]: target };
    // Deduplicate: clear any other column that was mapped to the same target
    if (target) {
      for (const [k, v] of Object.entries(next)) {
        if (k !== col && v === target) next[k] = null;
      }
    }
    setMapping(next);
  }

  return (
    <div className="space-y-5">
      <CardShell
        title={`2. Map ${headers.length} columns`}
        subtitle={`Detected ${mappedCount} of ${headers.length} columns. Adjust any that look wrong.`}
      >
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] uppercase tracking-wider text-[#71717A] border-b border-[rgba(255,255,255,0.05)]">
                <th className="py-2 pr-4 font-medium">CSV column</th>
                <th className="py-2 pr-4 font-medium">Sample</th>
                <th className="py-2 font-medium">Maps to</th>
              </tr>
            </thead>
            <tbody>
              {headers.map((h) => {
                const sample = preview.slice(0, 3).map((r) => r[h]).filter(Boolean).slice(0, 2).join(" · ");
                return (
                  <tr key={h} className="border-b border-[rgba(255,255,255,0.04)]">
                    <td className="py-2 pr-4 font-mono text-[13px] text-white whitespace-nowrap">{h}</td>
                    <td className="py-2 pr-4 text-[#B0B8C8] max-w-[260px] truncate" title={sample}>
                      {sample || <span className="text-[#71717A]">—</span>}
                    </td>
                    <td className="py-2">
                      <select
                        value={mapping[h] ?? ""}
                        onChange={(e) => setCol(h, (e.target.value || null) as CrmTargetField | null)}
                        className="px-2 py-1.5 text-sm rounded-md bg-[#0A0F1A] border border-[rgba(255,255,255,0.08)] text-white focus:outline-none focus:border-[rgba(255,109,90,0.4)]"
                      >
                        <option value="">Skip this column</option>
                        {groups.map((g) => (
                          <optgroup key={g.label} label={g.label}>
                            {g.fields.map((f) => {
                              const disabled = mapping[h] !== f.key && usedTargets.has(f.key);
                              return (
                                <option key={f.key} value={f.key} disabled={disabled}>
                                  {f.label}
                                  {f.required ? " *" : ""}
                                </option>
                              );
                            })}
                          </optgroup>
                        ))}
                      </select>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </CardShell>

      <CardShell title="Preview (first 5 rows)">
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-[#71717A] border-b border-[rgba(255,255,255,0.05)]">
                {headers.map((h) => (
                  <th key={h} className="py-2 px-3 font-medium whitespace-nowrap">
                    {h}
                    {mapping[h] && (
                      <div className="text-[9px] text-[#FF6D5A] normal-case tracking-normal mt-0.5">
                        → {mapping[h]}
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {preview.slice(0, 5).map((row, i) => (
                <tr key={i} className="border-b border-[rgba(255,255,255,0.04)]">
                  {headers.map((h) => (
                    <td key={h} className="py-1.5 px-3 text-[#B0B8C8] max-w-[200px] truncate">
                      {row[h] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardShell>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onIngest}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium border border-[rgba(255,109,90,0.35)] bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.22)] transition-colors"
        >
          <CheckCircle2 size={14} />
          Ingest {rowsTotal.toLocaleString()} rows
        </button>
        <button
          type="button"
          onClick={onReset}
          className="px-3 py-2 rounded-lg text-sm text-[#B0B8C8] hover:text-white hover:bg-[rgba(255,255,255,0.04)]"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}

function DoneStep({
  ingested,
  failed,
  errors,
  onAnother,
  onViewLeads,
}: {
  ingested: number;
  failed: number;
  errors: Array<{ row: number; reason: string }>;
  onAnother: () => void;
  onViewLeads: () => void;
}) {
  return (
    <CardShell>
      <div className="flex items-start gap-4">
        <div className="w-10 h-10 rounded-full grid place-items-center bg-[rgba(16,185,129,0.15)] border border-[rgba(16,185,129,0.35)] flex-shrink-0">
          <CheckCircle2 size={18} className="text-[#10B981]" />
        </div>
        <div className="flex-1">
          <h3 className="text-[15px] font-semibold text-white">Import complete</h3>
          <p className="mt-1 text-sm text-[#B0B8C8]">
            {ingested.toLocaleString()} lead{ingested === 1 ? "" : "s"} added to your CRM
            {failed > 0 ? ` — ${failed.toLocaleString()} row${failed === 1 ? "" : "s"} skipped` : ""}.
          </p>

          {errors.length > 0 && (
            <details className="mt-3">
              <summary className="text-xs text-[#FF6D5A] cursor-pointer">
                Show first {Math.min(5, errors.length)} skipped rows
              </summary>
              <ul className="mt-2 space-y-1 text-xs text-[#B0B8C8]">
                {errors.slice(0, 5).map((e, i) => (
                  <li key={i} className="font-mono">
                    Row {e.row}: {e.reason}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <div className="mt-4 flex items-center gap-2">
            <button
              type="button"
              onClick={onViewLeads}
              className="px-4 py-2 rounded-lg text-sm font-medium border border-[rgba(255,109,90,0.35)] bg-[rgba(255,109,90,0.15)] text-[#FF6D5A] hover:bg-[rgba(255,109,90,0.22)]"
            >
              View leads →
            </button>
            <button
              type="button"
              onClick={onAnother}
              className="px-4 py-2 rounded-lg text-sm text-white bg-[rgba(255,255,255,0.05)] hover:bg-[rgba(255,255,255,0.08)]"
            >
              Import another file
            </button>
          </div>
        </div>
      </div>
    </CardShell>
  );
}
