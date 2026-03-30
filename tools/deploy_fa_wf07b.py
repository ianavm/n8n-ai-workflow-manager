"""
FA-07b: Send Communications (On-Demand)

Webhook-triggered workflow for sending communications via email,
WhatsApp, or Teams. Logs all communications in Supabase.

Usage:
    python tools/deploy_fa_wf07b.py build
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fa_helpers import (
    build_workflow,
    code_node,
    conn,
    outlook_send_node,
    respond_to_webhook_node,
    supabase_insert_node,
    supabase_query_node,
    switch_node,
    teams_message_node,
    webhook_node,
    whatsapp_template_node,
)


FA_FIRM_ID = os.getenv("FA_FIRM_ID", "ea0fbe19-4612-414a-b00f-f1ce185a1ea3")


def build_nodes() -> list[dict]:
    """Build all nodes for FA-07b Send Communications."""
    nodes = []

    # -- 1. Webhook trigger --------------------------------------
    nodes.append(webhook_node(
        "Webhook Trigger",
        "advisory/send-comm",
        [0, 0],
    ))

    # -- 2. Validate input ---------------------------------------
    nodes.append(code_node(
        "Validate Input",
        """
const body = $input.first().json.body || $input.first().json;
const required = ['client_id', 'channel', 'template_name'];
const missing = required.filter(f => !body[f]);

if (missing.length > 0) {
  throw new Error('Missing required fields: ' + missing.join(', '));
}

const validChannels = ['email', 'whatsapp', 'teams'];
if (!validChannels.includes(body.channel)) {
  throw new Error('Invalid channel: ' + body.channel + '. Must be one of: ' + validChannels.join(', '));
}

return [{json: {
  client_id: body.client_id,
  channel: body.channel,
  template_name: body.template_name,
  subject: body.subject || '',
  body: body.body || '',
  variables: body.variables || {},
  adviser_id: body.adviser_id || null,
  meeting_id: body.meeting_id || null,
}}];
""",
        [300, 0],
    ))

    # -- 3. Fetch client details ---------------------------------
    nodes.append(supabase_query_node(
        "Fetch Client",
        "fa_clients",
        "id=eq.{{ $json.client_id }}&select=id,first_name,last_name,email,mobile",
        [600, 0],
    ))

    # -- 4. Switch on channel ------------------------------------
    nodes.append(switch_node(
        "Route Channel",
        [
            {
                "conditions": {
                    "conditions": [{
                        "leftValue": "={{ $('Validate Input').first().json.channel }}",
                        "rightValue": "email",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                },
                "output": 0,
            },
            {
                "conditions": {
                    "conditions": [{
                        "leftValue": "={{ $('Validate Input').first().json.channel }}",
                        "rightValue": "whatsapp",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                },
                "output": 1,
            },
            {
                "conditions": {
                    "conditions": [{
                        "leftValue": "={{ $('Validate Input').first().json.channel }}",
                        "rightValue": "teams",
                        "operator": {"type": "string", "operation": "equals"},
                    }],
                },
                "output": 2,
            },
        ],
        [900, 0],
    ))

    # -- 5. Send email -------------------------------------------
    nodes.append(outlook_send_node(
        "Send Email",
        "={{ $('Fetch Client').first().json[0].email }}",
        "={{ $('Validate Input').first().json.subject }}",
        "={{ $('Validate Input').first().json.body }}",
        [1200, -200],
    ))

    # -- 6. Send WhatsApp ----------------------------------------
    nodes.append(whatsapp_template_node(
        "Send WhatsApp",
        "{{ $('Fetch Client').first().json[0].mobile }}",
        "={{ $('Validate Input').first().json.template_name }}",
        """={{ JSON.stringify(
  Object.values($('Validate Input').first().json.variables).map(v => ({type: 'text', text: String(v)}))
) }}""",
        [1200, 0],
    ))

    # -- 7. Send Teams message -----------------------------------
    nodes.append(teams_message_node(
        "Send Teams",
        "={{ $env.FA_TEAMS_CHANNEL_ID }}",
        "={{ $('Validate Input').first().json.body }}",
        [1200, 200],
    ))

    # -- 8. Log communication ------------------------------------
    nodes.append(supabase_insert_node(
        "Log Communication",
        "fa_communications",
        f"""={{{{
  JSON.stringify({{
    client_id: $('Validate Input').first().json.client_id,
    firm_id: '{FA_FIRM_ID}',
    adviser_id: $('Validate Input').first().json.adviser_id,
    meeting_id: $('Validate Input').first().json.meeting_id,
    channel: $('Validate Input').first().json.channel,
    direction: 'outbound',
    subject: $('Validate Input').first().json.subject || $('Validate Input').first().json.template_name,
    whatsapp_template: $('Validate Input').first().json.channel === 'whatsapp' ? $('Validate Input').first().json.template_name : null,
    status: 'sent',
    sent_at: new Date().toISOString()
  }})
}}}}""",
        [1500, 0],
    ))

    # -- 9. Respond to webhook -----------------------------------
    nodes.append(respond_to_webhook_node(
        "Respond Success",
        """={{ JSON.stringify({
  success: true,
  communication_id: $json[0]?.id || null,
  channel: $('Validate Input').first().json.channel,
  client_id: $('Validate Input').first().json.client_id
}) }}""",
        [1800, 0],
    ))

    return nodes


def build_connections() -> dict:
    """Build connection map for FA-07b."""
    return {
        "Webhook Trigger": {"main": [[conn("Validate Input")]]},
        "Validate Input": {"main": [[conn("Fetch Client")]]},
        "Fetch Client": {"main": [[conn("Route Channel")]]},
        "Route Channel": {"main": [
            [conn("Send Email")],
            [conn("Send WhatsApp")],
            [conn("Send Teams")],
        ]},
        "Send Email": {"main": [[conn("Log Communication")]]},
        "Send WhatsApp": {"main": [[conn("Log Communication")]]},
        "Send Teams": {"main": [[conn("Log Communication")]]},
        "Log Communication": {"main": [[conn("Respond Success")]]},
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python deploy_fa_wf07b.py <build|deploy>")
        sys.exit(1)

    nodes = build_nodes()
    connections = build_connections()
    workflow = build_workflow(
        "FA - Send Communications (FA-07b)",
        nodes, connections,
        tags=["financial_advisory"],
    )

    output_dir = Path(__file__).parent.parent / "workflows" / "financial-advisory"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "fa07b_send_communications.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(workflow, f, indent=2, ensure_ascii=False)
    print(f"Built: {path} ({len(nodes)} nodes)")


if __name__ == "__main__":
    main()
