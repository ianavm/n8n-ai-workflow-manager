import { Workflow } from "lucide-react";
import { PageHeader } from "@/components/crm/PageHeader";
import { EmptyState } from "@/components/crm/EmptyState";
import { CardShell } from "@/components/crm/CardShell";

export default function AgentsPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Agents"
        description="Visual canvas of the scraping, enrichment, research, scoring, and outreach agents running on your pipeline."
      />
      <CardShell>
        <EmptyState
          icon={Workflow}
          title="Agent canvas — coming in Phase 2"
          description="This will show a live node graph with per-node run status, tokens, and cost. For now, agents run via n8n and your AVM team manages them directly."
        />
      </CardShell>
    </div>
  );
}
