"""
FA-06: Discovery-to-Presentation Pipeline

Sub-workflow called by FA-05.  Receives {client_id, meeting_id, adviser_id}.
Gathers full client data, runs AI gap-analysis + product recommendations,
generates a FAIS-compliant Record of Advice draft, stores pricing records,
notifies the adviser, and schedules a presentation meeting via FA-02.

Usage:
    python tools/deploy_fa_wf06.py build
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fa_helpers import (
    ai_analysis_node,
    build_workflow,
    code_node,
    conn,
    execute_workflow_node,
    execute_workflow_trigger_node,
    outlook_send_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")
FA_WF02_ID = os.getenv("FA_WF02_ID", "REPLACE_WITH_FA02_WORKFLOW_ID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-06 Discovery-to-Presentation Pipeline."""
    nodes: list[dict] = []

    # -- 1. Execute Workflow Trigger ---------------------------
    nodes.append(execute_workflow_trigger_node(
        "Workflow Trigger",
        [0, 0],
    ))

    # -- 2. Fetch Full Client Data -----------------------------
    nodes.append(supabase_query_node(
        "Fetch Full Client",
        "fa_clients",
        (
            "id=eq.{{ $json.client_id }}"
            "&select=*,"
            "dependents:fa_dependents(*),"
            "products:fa_client_products(*),"
            "insights:fa_meeting_insights(*)"
        ),
        [300, 0],
        select="*,dependents:fa_dependents(*),products:fa_client_products(*),insights:fa_meeting_insights(*)",
    ))

    # -- 3. AI Research Analysis -------------------------------
    system_prompt_research = (
        "Analyze this South African client's financial situation. "
        "Identify gaps in coverage, recommend specific products from the "
        "provider list, prioritize needs based on urgency and budget, "
        "consider risk tolerance. Output as JSON: "
        "{recommendations: [{product_type, provider, rationale, priority, estimated_premium}], "
        "gap_analysis: string, risk_assessment: string}"
    )
    user_prompt_research = (
        "\"Full client data for analysis: \""
        " + JSON.stringify($('Fetch Full Client').first().json[0])"
    )
    nodes.append(ai_analysis_node(
        "Research Analysis",
        system_prompt_research,
        user_prompt_research,
        [600, 0],
        max_tokens=5000,
    ))

    # -- 4. AI Record of Advice Draft --------------------------
    system_prompt_roa = (
        "Draft a FAIS-compliant Record of Advice for this South African "
        "client. Include: client needs analysis, recommendations with "
        "rationale, risk disclosures, fee disclosure, alternative products "
        "considered. Format as professional HTML document."
    )
    user_prompt_roa = (
        "\"Client data: \" + JSON.stringify($('Fetch Full Client').first().json[0])"
        " + \"\\n\\nResearch analysis: \" + JSON.stringify($('Research Analysis').first().json.choices?.[0]?.message?.content || '')"
    )
    nodes.append(ai_analysis_node(
        "Generate Record of Advice",
        system_prompt_roa,
        user_prompt_roa,
        [900, 0],
        max_tokens=6000,
    ))

    # -- 5. Store Advice Document Reference --------------------
    nodes.append(supabase_insert_node(
        "Store Advice Doc",
        "fa_documents",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Workflow Trigger').first().json.client_id,
    adviser_id: $('Workflow Trigger').first().json.adviser_id,
    firm_id: '{FA_FIRM_ID}',
    meeting_id: $('Workflow Trigger').first().json.meeting_id,
    document_type: 'record_of_advice',
    title: 'Record of Advice - ' + ($('Fetch Full Client').first().json[0].first_name || '') + ' ' + ($('Fetch Full Client').first().json[0].last_name || ''),
    content: $('Generate Record of Advice').first().json.choices?.[0]?.message?.content || '',
    status: 'draft',
    version: 1
  }})
}}}}""",
        [1200, 0],
    ))

    # -- 6. Calculate Recommended Pricing ----------------------
    nodes.append(code_node(
        "Build Pricing Records",
        f"""
// Parse research analysis to extract recommendations with pricing
const raw = $('Research Analysis').first().json.choices?.[0]?.message?.content || '{{}}';
let analysis;
try {{
  const jsonMatch = raw.match(/```json\\n?([\\s\\S]*?)```/) || raw.match(/\\{{[\\s\\S]*\\}}/);
  analysis = JSON.parse(jsonMatch ? (jsonMatch[1] || jsonMatch[0]) : raw);
}} catch (e) {{
  analysis = {{recommendations: []}};
}}

const recommendations = analysis.recommendations || [];
const clientId = $('Workflow Trigger').first().json.client_id;
const adviserId = $('Workflow Trigger').first().json.adviser_id;

const pricingRecords = recommendations.map((rec, idx) => ({{
  client_id: clientId,
  adviser_id: adviserId,
  firm_id: '{FA_FIRM_ID}',
  product_type: rec.product_type || 'unknown',
  provider: rec.provider || 'TBD',
  estimated_premium: rec.estimated_premium || 0,
  rationale: rec.rationale || '',
  priority: rec.priority || 'medium',
  status: 'draft',
  sort_order: idx + 1
}}));

return [{{json: {{pricing: pricingRecords, gap_analysis: analysis.gap_analysis || '', risk_assessment: analysis.risk_assessment || ''}}}}];
""",
        [1500, 0],
    ))

    # -- 7. Insert Pricing Records (batch) ---------------------
    nodes.append(supabase_insert_node(
        "Store Pricing",
        "fa_pricing",
        "={{ JSON.stringify($json.pricing) }}",
        [1800, 0],
    ))

    # -- 8. Update Pipeline Stage -> analysis ------------------
    nodes.append(supabase_update_node(
        "Pipeline Analysis",
        "fa_clients",
        "id",
        "={{ $('Workflow Trigger').first().json.client_id }}",
        """={{ JSON.stringify({
  pipeline_stage: 'analysis',
  pipeline_updated_at: new Date().toISOString()
}) }}""",
        [2100, 0],
    ))

    # -- 9. Notify Adviser via Email ---------------------------
    nodes.append(outlook_send_node(
        "Notify Adviser",
        "={{ $('Fetch Full Client').first().json[0]?.insights?.[0]?.adviser?.email || $('Workflow Trigger').first().json.adviser_id }}",
        "=Analysis Complete: {{ $('Fetch Full Client').first().json[0].first_name }} {{ $('Fetch Full Client').first().json[0].last_name }}",
        """={{ (function() {
  const client = $('Fetch Full Client').first().json[0];
  const pricing = $('Build Pricing Records').first().json.pricing || [];
  const gap = $('Build Pricing Records').first().json.gap_analysis || 'See full report';
  return `<h2>Analysis Complete</h2>
  <p>The discovery analysis for <strong>${client.first_name} ${client.last_name}</strong> is ready for your review.</p>
  <h3>Gap Analysis</h3>
  <p>${gap}</p>
  <h3>Recommendations (${pricing.length})</h3>
  <ul>${pricing.map(p => `<li><strong>${p.product_type}</strong> - ${p.provider} (est. R${p.estimated_premium}/mo) - ${p.rationale}</li>`).join('')}</ul>
  <p>Please review the Record of Advice draft before the presentation meeting.</p>
  <p style="text-align:center;margin-top:20px;"><a href="#" style="display:inline-block;background:#FF6D5A;color:#fff;padding:14px 32px;border-radius:8px;text-decoration:none;font-weight:600;">Review in Portal</a></p>`;
})() }}""",
        [2400, 0],
    ))

    # -- 10. Schedule Presentation Meeting via FA-02 -----------
    nodes.append(execute_workflow_node(
        "Schedule Presentation",
        FA_WF02_ID,
        [2700, 0],
        input_data_expr="={{ JSON.stringify({ client_id: $('Workflow Trigger').first().json.client_id, adviser_id: $('Workflow Trigger').first().json.adviser_id, meeting_type: 'presentation' }) }}",
    ))

    # -- 11. Update Pipeline -> presentation_scheduled ---------
    nodes.append(supabase_update_node(
        "Pipeline Presentation Scheduled",
        "fa_clients",
        "id",
        "={{ $('Workflow Trigger').first().json.client_id }}",
        """={{ JSON.stringify({
  pipeline_stage: 'presentation_scheduled',
  pipeline_updated_at: new Date().toISOString()
}) }}""",
        [3000, 0],
    ))

    # -- 12. Log Adviser Notification --------------------------
    nodes.append(supabase_insert_node(
        "Log Notification",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Workflow Trigger').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $('Workflow Trigger').first().json.adviser_id,
    meeting_id: $('Workflow Trigger').first().json.meeting_id,
    channel: 'email',
    direction: 'outbound',
    subject: 'Analysis Complete Notification',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [2400, 200],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-06."""
    return {
        "Workflow Trigger": {"main": [[conn("Fetch Full Client")]]},
        "Fetch Full Client": {"main": [[conn("Research Analysis")]]},
        "Research Analysis": {"main": [[conn("Generate Record of Advice")]]},
        "Generate Record of Advice": {"main": [[conn("Store Advice Doc")]]},
        "Store Advice Doc": {"main": [[conn("Build Pricing Records")]]},
        "Build Pricing Records": {"main": [[conn("Store Pricing")]]},
        "Store Pricing": {"main": [[conn("Pipeline Analysis")]]},
        "Pipeline Analysis": {"main": [[conn("Notify Adviser"), conn("Log Notification")]]},
        "Notify Adviser": {"main": [[conn("Schedule Presentation")]]},
        "Schedule Presentation": {"main": [[conn("Pipeline Presentation Scheduled")]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf06.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Discovery to Presentation (FA-06)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa06_discovery_pipeline.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
