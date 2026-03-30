"""
FA-05: Post-Meeting Processing

Sub-workflow called by FA-04.  Receives {meeting_id, client_id}.
Generates a client-friendly summary, emails it, creates tasks from
action items, logs the communication, and optionally triggers FA-06
(discovery pipeline) or FA-02 (follow-up meeting).

Usage:
    python tools/deploy_fa_wf05.py build
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
    if_node,
    outlook_send_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")
FA_WF02_ID = os.getenv("FA_WF02_ID", "REPLACE_WITH_FA02_WORKFLOW_ID")
FA_WF06_ID = os.getenv("FA_WF06_ID", "REPLACE_WITH_FA06_WORKFLOW_ID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-05 Post-Meeting Processing."""
    nodes: list[dict] = []

    # -- 1. Execute Workflow Trigger ---------------------------
    nodes.append(execute_workflow_trigger_node(
        "Workflow Trigger",
        [0, 0],
    ))

    # -- 2. Fetch Meeting + Insights ---------------------------
    nodes.append(supabase_query_node(
        "Fetch Meeting",
        "fa_meetings",
        (
            "id=eq.{{ $json.meeting_id }}"
            "&select=*,insights:fa_meeting_insights(*),client:fa_clients(*),adviser:fa_advisers(*)"
        ),
        [300, 0],
        select="*,insights:fa_meeting_insights(*),client:fa_clients(*),adviser:fa_advisers(*)",
    ))

    # -- 3. AI Client Summary ----------------------------------
    system_prompt = (
        "You are a financial advisory assistant. Generate a professional, "
        "client-friendly meeting summary email. Exclude compliance_flags and "
        "internal notes. Include: discussion points recap, agreed next steps, "
        "action items with owners. Use warm but professional tone. "
        "Output as HTML suitable for email."
    )
    user_prompt_expr = (
        "\"Generate client meeting summary for: \""
        " + JSON.stringify({"
        "  meeting: $('Fetch Meeting').first().json[0],"
        "  insights: $('Fetch Meeting').first().json[0]?.insights?.[0] || {}"
        "})"
    )
    nodes.append(ai_analysis_node(
        "Generate Client Summary",
        system_prompt,
        user_prompt_expr,
        [600, 0],
        max_tokens=3000,
    ))

    # -- 4. Send Summary Email to Client -----------------------
    nodes.append(outlook_send_node(
        "Email Client Summary",
        "={{ $('Fetch Meeting').first().json[0].client.email }}",
        "=Meeting Summary: {{ $('Fetch Meeting').first().json[0].title || $('Fetch Meeting').first().json[0].meeting_type + ' Meeting' }}",
        "={{ $('Generate Client Summary').first().json.choices?.[0]?.message?.content || '<p>Meeting summary is being prepared.</p>' }}",
        [900, 0],
    ))

    # -- 5. Transform Action Items into Task Records -----------
    nodes.append(code_node(
        "Build Task Records",
        f"""
// Extract action items from meeting insights and build task records
const meeting = $('Fetch Meeting').first().json[0];
const insights = meeting?.insights?.[0] || {{}};
const actionItems = insights.action_items || [];

const tasks = actionItems.map((item, idx) => ({{
  client_id: meeting.client_id,
  adviser_id: meeting.adviser_id,
  firm_id: '{FA_FIRM_ID}',
  meeting_id: meeting.id,
  title: item.task || 'Action item ' + (idx + 1),
  description: item.task,
  assignee: item.assignee || 'adviser',
  due_date: item.suggested_due_date || new Date(Date.now() + 7*24*60*60*1000).toISOString().split('T')[0],
  status: 'pending',
  priority: 'medium'
}}));

return [{{json: {{tasks}}}}];
""",
        [1200, 0],
    ))

    # -- 6. Insert Tasks (batch) -------------------------------
    nodes.append(supabase_insert_node(
        "Store Tasks",
        "fa_tasks",
        "={{ JSON.stringify($json.tasks) }}",
        [1500, 0],
    ))

    # -- 7. Log Summary Email Communication --------------------
    nodes.append(supabase_insert_node(
        "Log Communication",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Fetch Meeting').first().json[0].client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $('Fetch Meeting').first().json[0].adviser_id,
    meeting_id: $('Fetch Meeting').first().json[0].id,
    channel: 'email',
    direction: 'outbound',
    subject: 'Post-Meeting Summary',
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [1500, 200],
    ))

    # -- 8. Is Discovery Meeting? ------------------------------
    nodes.append(if_node(
        "Is Discovery",
        [
            {
                "leftValue": "={{ $('Fetch Meeting').first().json[0].meeting_type }}",
                "rightValue": "discovery",
                "operator": {
                    "type": "string",
                    "operation": "equals",
                },
            }
        ],
        [1800, 0],
    ))

    # -- 9. Trigger FA-06 (TRUE branch: discovery) -------------
    nodes.append(execute_workflow_node(
        "Trigger FA-06",
        FA_WF06_ID,
        [2100, -100],
        input_data_expr="={{ JSON.stringify({ client_id: $('Fetch Meeting').first().json[0].client_id, meeting_id: $('Fetch Meeting').first().json[0].id, adviser_id: $('Fetch Meeting').first().json[0].adviser_id }) }}",
    ))

    # -- 10. Update Pipeline Stage -> discovery_complete -------
    nodes.append(supabase_update_node(
        "Pipeline Discovery Complete",
        "fa_clients",
        "id",
        "={{ $('Fetch Meeting').first().json[0].client_id }}",
        """={{ JSON.stringify({
  pipeline_stage: 'discovery_complete',
  pipeline_updated_at: new Date().toISOString()
}) }}""",
        [2100, -300],
    ))

    # -- 11. Follow-Up Needed? ---------------------------------
    nodes.append(if_node(
        "Follow Up Needed",
        [
            {
                "leftValue": "={{ JSON.stringify($('Fetch Meeting').first().json[0]?.insights?.[0]?.next_steps || '').toLowerCase() }}",
                "rightValue": "follow",
                "operator": {
                    "type": "string",
                    "operation": "contains",
                },
            }
        ],
        [1800, 300],
    ))

    # -- 12. Trigger FA-02 for Follow-Up Meeting ---------------
    nodes.append(execute_workflow_node(
        "Schedule Follow-Up",
        FA_WF02_ID,
        [2100, 300],
        input_data_expr="={{ JSON.stringify({ client_id: $('Fetch Meeting').first().json[0].client_id, adviser_id: $('Fetch Meeting').first().json[0].adviser_id, meeting_type: 'follow_up' }) }}",
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-05."""
    return {
        "Workflow Trigger": {"main": [[conn("Fetch Meeting")]]},
        "Fetch Meeting": {"main": [[conn("Generate Client Summary")]]},
        "Generate Client Summary": {"main": [[conn("Email Client Summary")]]},
        "Email Client Summary": {"main": [[conn("Build Task Records"), conn("Log Communication")]]},
        "Build Task Records": {"main": [[conn("Store Tasks")]]},
        "Store Tasks": {"main": [[conn("Is Discovery"), conn("Follow Up Needed")]]},
        "Is Discovery": {"main": [[conn("Trigger FA-06"), conn("Pipeline Discovery Complete")], []]},
        "Follow Up Needed": {"main": [[conn("Schedule Follow-Up")], []]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf05.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Post-Meeting Processing (FA-05)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa05_post_meeting.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
