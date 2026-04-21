"""
FA-03: Pre-Meeting Prep

Hourly (06-18 weekdays) checks for meetings in the next 90-150 min window,
gathers client data (products, dependents, past insights), generates a
briefing via AI, then emails and Teams-messages it to the adviser.

Usage:
    python tools/deploy_fa_wf03.py build
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
    if_node,
    outlook_send_node,
    schedule_node,
    split_in_batches_node,
    supabase_query_node,
    teams_message_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-03 Pre-Meeting Prep."""
    nodes: list[dict] = []

    # -- 1. Schedule Trigger (hourly 06-18 weekdays) -----------
    nodes.append(schedule_node(
        "Schedule Trigger",
        "0 * 6-18 * * 1-5",
        [0, 0],
    ))

    # -- 2. Fetch Upcoming Meetings ----------------------------
    nodes.append(supabase_query_node(
        "Fetch Upcoming Meetings",
        "fa_meetings",
        (
            "status=in.(scheduled,confirmed)"
            "&scheduled_at=gte.{{ new Date(Date.now() + 90*60*1000).toISOString() }}"
            "&scheduled_at=lte.{{ new Date(Date.now() + 150*60*1000).toISOString() }}"
            "&select=*,client:fa_clients(*),adviser:fa_advisers(*)"
        ),
        [300, 0],
        select="*,client:fa_clients(*),adviser:fa_advisers(*)",
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

    # -- 5. Fetch Client Products ------------------------------
    nodes.append(supabase_query_node(
        "Fetch Products",
        "fa_client_products",
        "client_id=eq.{{ $json.client_id }}",
        [1200, 0],
    ))

    # -- 6. Fetch Dependents -----------------------------------
    nodes.append(supabase_query_node(
        "Fetch Dependents",
        "fa_dependents",
        "client_id=eq.{{ $json.client_id }}",
        [1200, 200],
    ))

    # -- 7. Fetch Past Meeting Insights ------------------------
    nodes.append(supabase_query_node(
        "Fetch Past Insights",
        "fa_meeting_insights",
        (
            "meeting_id=in.("
            "select id from fa_meetings "
            "where client_id=eq.{{ $('Loop Meetings').first().json.client_id }}"
            ")&order=created_at.desc&limit=5"
        ),
        [1200, -200],
    ))

    # -- 8. AI Briefing ----------------------------------------
    system_prompt = (
        "You are a financial advisory AI assistant. "
        "Generate a comprehensive pre-meeting briefing for the adviser. "
        "Include: executive summary, client financial profile overview, "
        "existing products analysis, identified gaps, previous meeting insights, "
        "suggested talking points, risk flags."
    )
    user_prompt_expr = (
        "\"Pre-meeting briefing for: \""
        " + JSON.stringify({"
        "  meeting: $('Loop Meetings').first().json,"
        "  products: $('Fetch Products').all().map(i => i.json),"
        "  dependents: $('Fetch Dependents').all().map(i => i.json),"
        "  past_insights: $('Fetch Past Insights').all().map(i => i.json)"
        "})"
    )
    nodes.append(ai_analysis_node(
        "Generate Briefing",
        system_prompt,
        user_prompt_expr,
        [1500, 0],
        max_tokens=4000,
    ))

    # -- 9. Send Briefing Email --------------------------------
    nodes.append(outlook_send_node(
        "Email Briefing",
        "={{ $('Loop Meetings').first().json.adviser.email }}",
        "=Pre-Meeting Briefing: {{ $('Loop Meetings').first().json.client.first_name }} {{ $('Loop Meetings').first().json.client.last_name }}",
        """={{ (function() {
  const meeting = $('Loop Meetings').first().json;
  const briefing = $('Generate Briefing').first().json.choices?.[0]?.message?.content || 'No briefing generated';
  return `<h2>Pre-Meeting Briefing</h2>
  <p><strong>Client:</strong> ${meeting.client.first_name} ${meeting.client.last_name}</p>
  <p><strong>Meeting Type:</strong> ${meeting.meeting_type}</p>
  <p><strong>Scheduled:</strong> ${new Date(meeting.scheduled_at).toLocaleString('en-ZA', {timeZone: 'Africa/Johannesburg'})}</p>
  <hr/>
  <div>${briefing.replace(/\\n/g, '<br/>')}</div>`;
})() }}""",
        [1800, -100],
    ))

    # -- 10. Teams Message -------------------------------------
    nodes.append(teams_message_node(
        "Teams Briefing",
        "={{ $('Loop Meetings').first().json.adviser.microsoft_user_id }}",
        """={{ (function() {
  const meeting = $('Loop Meetings').first().json;
  const briefing = $('Generate Briefing').first().json.choices?.[0]?.message?.content || '';
  const summary = briefing.substring(0, 500) + (briefing.length > 500 ? '...' : '');
  return `<b>Pre-Meeting Briefing: ${meeting.client.first_name} ${meeting.client.last_name}</b><br/>`
    + `<b>Type:</b> ${meeting.meeting_type} | <b>Time:</b> ${new Date(meeting.scheduled_at).toLocaleString('en-ZA', {timeZone: 'Africa/Johannesburg'})}<br/>`
    + `<br/>${summary}<br/><br/><i>Full briefing sent via email.</i>`;
})() }}""",
        [1800, 100],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-03."""
    return {
        "Schedule Trigger": {"main": [[conn("Fetch Upcoming Meetings")]]},
        "Fetch Upcoming Meetings": {"main": [[conn("Has Meetings")]]},
        "Has Meetings": {"main": [[conn("Loop Meetings")], []]},
        "Loop Meetings": {"main": [[], [conn("Fetch Products"), conn("Fetch Dependents"), conn("Fetch Past Insights")]]},
        "Fetch Products": {"main": [[conn("Generate Briefing")]]},
        "Generate Briefing": {"main": [[conn("Email Briefing"), conn("Teams Briefing")]]},
        "Email Briefing": {"main": [[conn("Loop Meetings", index=0)]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf03.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Pre-Meeting Prep (FA-03)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa03_pre_meeting_prep.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
