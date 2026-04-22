import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { ImportWizard } from "@/components/crm/ImportWizard";

export default function NewImportPage() {
  return (
    <div className="space-y-6">
      <Link
        href="/portal/crm/imports"
        className="inline-flex items-center gap-1.5 text-xs text-[#B0B8C8] hover:text-white"
      >
        <ArrowLeft size={12} />
        Back to imports
      </Link>

      <PageHeader
        title="Import from existing CRM"
        description="Upload a CSV exported from your current CRM (HubSpot, Pipedrive, Salesforce, Zoho, Apollo, or anywhere else). We auto-detect columns — you confirm, we ingest."
      />

      <ImportWizard />
    </div>
  );
}
