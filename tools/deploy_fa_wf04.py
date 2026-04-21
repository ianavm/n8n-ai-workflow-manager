"""
FA-04: Meeting Recording & Transcription

Every 15 min (06-20 weekdays) checks for completed meetings missing
transcripts, fetches Teams meeting transcripts via Graph API, runs AI
analysis to extract structured insights, stores everything in Supabase,
then triggers FA-05 for post-meeting processing.

Usage:
    python tools/deploy_fa_wf04.py build
"""

from __future__ import annotations

import json
import os
from dotenv import load_dotenv

load_dotenv()
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fa_helpers import (
    ai_analysis_node,
    build_workflow,
    code_node,
    conn,
    execute_workflow_node,
    graph_api_node,
    if_node,
    schedule_node,
    split_in_batches_node,
    supabase_insert_node,
    supabase_query_node,
    supabase_update_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")
FA_WF05_ID = os.getenv("FA_WF05_ID", "REPLACE_WITH_FA05_WORKFLOW_ID")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-04 Meeting Recording & Transcription."""
    nodes: list[dict] = []

    # -- 1. Schedule Trigger (every 15min 06-20 weekdays) ------
    nodes.append(schedule_node(
        "Schedule Trigger",
        "*/15 6-20 * * 1-5",
        [0, 0],
    ))

    # -- 2. Fetch Completed Meetings ---------------------------
    nodes.append(supabase_query_node(
        "Fetch Completed Meetings",
        "fa_meetings",
        (
            "status=eq.completed"
            "&transcript_status=in.(none,pending)"
            "&ended_at=gte.{{ new Date(Date.now() - 48*60*60*1000).toISOString() }}"
            "&select=*,adviser:fa_advisers(id,full_name,email,microsoft_user_id)"
        ),
        [300, 0],
        select="*,adviser:fa_advisers(id,full_name,email,microsoft_user_id)",
    ))

    # -- 3. Has Results? ---------------------------------------
    nodes.append(if_node(
        "Has Meetings",
        [
            {
                "leftValue": "={{ $json.length }}",
                "rightValue": 0,
                "operator": {
                    "type": "number",
                    "operation": "gt",
                },
            }
        ],
        [600, 0],
    ))

    # -- 4. Split In Batches -----------------------------------
    nodes.append(split_in_batches_node(
        "Loop Meetings",
        [900, 0],
        batch_size=1,
    ))

    # -- 5. Resolve Meeting ID via Graph -----------------------
    nodes.append(graph_api_node(
        "Resolve Meeting ID",
        "GET",
        "=/users/{{ $json.adviser.microsoft_user_id }}/onlineMeetings?$filter=joinWebUrl eq '{{ encodeURIComponent($json.teams_meeting_url) }}'",
        [1200, 0],
    ))

    # -- 6. Meeting Found? -------------------------------------
    nodes.append(if_node(
        "Meeting Found",
        [
            {
                "leftValue": "={{ $json.value?.length }}",
                "rightValue": 0,
                "operator": {
                    "type": "number",
                    "operation": "gt",
                },
            }
        ],
        [1500, 0],
    ))

    # -- 7. Get Transcripts List (Beta) ------------------------
    nodes.append(graph_api_node(
        "Get Transcripts",
        "GET",
        "=/users/{{ $('Loop Meetings').first().json.adviser.microsoft_user_id }}/onlineMeetings/{{ $json.value[0].id }}/transcripts",
        [1800, 0],
        api_version="beta",
    ))

    # -- 8. Transcripts Available? -----------------------------
    nodes.append(if_node(
        "Transcripts Available",
        [
            {
                "leftValue": "={{ $json.value?.length }}",
                "rightValue": 0,
                "operator": {
                    "type": "number",
                    "operation": "gt",
                },
            }
        ],
        [2100, 0],
    ))

    # -- 9. Download Transcript Content (VTT) ------------------
    nodes.append(graph_api_node(
        "Download Transcript",
        "GET",
        "=/users/{{ $('Loop Meetings').first().json.adviser.microsoft_user_id }}/onlineMeetings/{{ $('Resolve Meeting ID').first().json.value[0].id }}/transcripts/{{ $json.value[0].id }}/content",
        [2400, 0],
        api_version="beta",
    ))

    # -- 10. Update Status -> processing -----------------------
    nodes.append(supabase_update_node(
        "Set Processing",
        "fa_meetings",
        "id",
        "={{ $('Loop Meetings').first().json.id }}",
        """={{ JSON.stringify({
  transcript_status: 'processing',
  updated_at: new Date().toISOString()
}) }}""",
        [2700, 0],
    ))

    # -- 11. AI Transcript Analysis ----------------------------
    system_prompt = (
        "Analyze this financial advisory meeting transcript. "
        "Extract as JSON: "
        "1. summary (2-3 paragraphs), "
        "2. priorities [{priority, details, urgency}], "
        "3. objections [{objection, response_given, resolved}], "
        "4. action_items [{task, assignee, suggested_due_date}], "
        "5. compliance_flags [{flag, severity, details}], "
        "6. research_needs [{topic, product_type, details}], "
        "7. client_sentiment, "
        "8. key_quotes [], "
        "9. risk_tolerance_indicated, "
        "10. next_steps"
    )
    user_prompt_expr = (
        "\"Transcript for meeting \" + $('Loop Meetings').first().json.id"
        " + \" (\" + $('Loop Meetings').first().json.meeting_type + \"):\\n\\n\""
        " + JSON.stringify($('Download Transcript').first().json)"
    )
    nodes.append(ai_analysis_node(
        "Analyze Transcript",
        system_prompt,
        user_prompt_expr,
        [3000, 0],
        max_tokens=6000,
    ))

    # -- 12. Parse AI Response ---------------------------------
    nodes.append(code_node(
        "Parse AI Response",
        """
// Extract JSON from AI response
const raw = $input.first().json.choices?.[0]?.message?.content || '{}';
let parsed;
try {
  // Handle markdown code blocks
  const jsonMatch = raw.match(/```json\\n?([\\s\\S]*?)```/) || raw.match(/\\{[\\s\\S]*\\}/);
  parsed = JSON.parse(jsonMatch ? (jsonMatch[1] || jsonMatch[0]) : raw);
} catch (e) {
  parsed = {
    summary: raw,
    priorities: [],
    objections: [],
    action_items: [],
    compliance_flags: [],
    research_needs: [],
    client_sentiment: 'unknown',
    key_quotes: [],
    risk_tolerance_indicated: 'unknown',
    next_steps: ''
  };
}

// Validate required fields
const defaults = {
  summary: '', priorities: [], objections: [], action_items: [],
  compliance_flags: [], research_needs: [], client_sentiment: 'unknown',
  key_quotes: [], risk_tolerance_indicated: 'unknown', next_steps: ''
};
for (const [k, v] of Object.entries(defaults)) {
  if (parsed[k] === undefined) parsed[k] = v;
}

return [{json: parsed}];
""",
        [3300, 0],
    ))

    # -- 13. Insert Meeting Insights ---------------------------
    nodes.append(supabase_insert_node(
        "Store Insights",
        "fa_meeting_insights",
        f"""={{{{
  JSON.stringify({{
    meeting_id: $('Loop Meetings').first().json.id,
    firm_id: '{FA_FIRM_ID}',
    summary: $json.summary,
    priorities: $json.priorities,
    objections: $json.objections,
    action_items: $json.action_items,
    compliance_flags: $json.compliance_flags,
    research_needs: $json.research_needs,
    client_sentiment: $json.client_sentiment,
    key_quotes: $json.key_quotes,
    risk_tolerance_indicated: $json.risk_tolerance_indicated,
    next_steps: $json.next_steps
  }})
}}}}""",
        [3600, 0],
    ))

    # -- 14. Update Meeting with Transcript --------------------
    nodes.append(supabase_update_node(
        "Store Transcript",
        "fa_meetings",
        "id",
        "={{ $('Loop Meetings').first().json.id }}",
        """={{ JSON.stringify({
  transcript_raw: $('Download Transcript').first().json,
  transcript_status: 'available',
  updated_at: new Date().toISOString()
}) }}""",
        [3900, 0],
    ))

    # -- 15. Trigger FA-05 Post-Meeting Processing -------------
    nodes.append(execute_workflow_node(
        "Trigger FA-05",
        FA_WF05_ID,
        [4200, 0],
        input_data_expr="={{ JSON.stringify({ meeting_id: $('Loop Meetings').first().json.id, client_id: $('Loop Meetings').first().json.client_id }) }}",
    ))

    # -- 16. Timeout: Mark Failed (FALSE branch from node 3) ---
    nodes.append(supabase_update_node(
        "Mark Transcript Failed",
        "fa_meetings",
        "id",
        "={{ $json.id }}",
        """={{ JSON.stringify({
  transcript_status: 'failed',
  updated_at: new Date().toISOString()
}) }}""",
        [900, 300],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-04."""
    return {
        "Schedule Trigger": {"main": [[conn("Fetch Completed Meetings")]]},
        "Fetch Completed Meetings": {"main": [[conn("Has Meetings")]]},
        "Has Meetings": {"main": [[conn("Loop Meetings")], []]},
        "Loop Meetings": {"main": [[], [conn("Resolve Meeting ID")]]},
        "Resolve Meeting ID": {"main": [[conn("Meeting Found")]]},
        "Meeting Found": {"main": [[conn("Get Transcripts")], [conn("Mark Transcript Failed")]]},
        "Get Transcripts": {"main": [[conn("Transcripts Available")]]},
        "Transcripts Available": {"main": [[conn("Download Transcript")], [conn("Loop Meetings", index=0)]]},
        "Download Transcript": {"main": [[conn("Set Processing")]]},
        "Set Processing": {"main": [[conn("Analyze Transcript")]]},
        "Analyze Transcript": {"main": [[conn("Parse AI Response")]]},
        "Parse AI Response": {"main": [[conn("Store Insights")]]},
        "Store Insights": {"main": [[conn("Store Transcript")]]},
        "Store Transcript": {"main": [[conn("Trigger FA-05")]]},
        "Trigger FA-05": {"main": [[conn("Loop Meetings", index=0)]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf04.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Meeting Recording & Transcription (FA-04)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa04_meeting_recording.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
