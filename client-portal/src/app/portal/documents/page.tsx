"use client";

import { Card } from "@/components/ui/Card";
import { FileText } from "lucide-react";

export default function DocumentsPage() {
  return (
    <div className="max-w-7xl space-y-6">
      <h1 className="text-2xl font-bold text-white">Documents</h1>
      <Card>
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <div className="w-14 h-14 rounded-2xl bg-[rgba(0,212,170,0.1)] border border-[rgba(0,212,170,0.2)] flex items-center justify-center mb-4">
            <FileText size={28} className="text-[#00D4AA]" />
          </div>
          <h2 className="text-lg font-semibold text-white mb-2">Documents Coming Soon</h2>
          <p className="text-sm text-[#6B7280] max-w-md">
            Upload, manage, and share documents with your team. Access contracts, reports, and automated document workflows.
          </p>
        </div>
      </Card>
    </div>
  );
}
