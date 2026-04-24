import { FileText } from "lucide-react";

import { PageHeader } from "@/components/portal/PageHeader";
import { EmptyState } from "@/components/portal/EmptyState";

export default function DocumentsPage() {
  return (
    <div className="flex flex-col gap-8">
      <PageHeader
        eyebrow="Operations"
        title="Documents"
        description="Upload, manage, and share documents with your team."
      />
      <EmptyState
        icon={<FileText className="size-5" />}
        title="Documents coming soon"
        description="Contracts, reports, and automated document workflows. Let us know if you need this sooner — we can move it up the roadmap."
      />
    </div>
  );
}
