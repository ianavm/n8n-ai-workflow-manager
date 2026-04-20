"""DEMO-11: Build-With-Me Minimal Pipeline.

Deliberately minimal. Six nodes, linear left-to-right, designed to be
built on camera in under 90 seconds:

    Webhook -> Demo Config -> AI Draft Reply -> Gmail Send
            -> Log to Sheet -> Respond

No switch, no demo/live branch, no fallback heuristics. The simplicity
IS the pitch — "this is all it takes".
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_vol2_shared import (  # noqa: E402
    DemoSpec,
    MODEL_SONNET,
    build_workflow_envelope,
    gmail_send,
    openrouter_call,
    respond_to_webhook,
    run_cli,
    set_demo_config,
    sheets_append,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-11 Build-With-Me Minimal Pipeline"
WORKFLOW_FILENAME = "demo11_build_with_me.json"
WEBHOOK_PATH = "demo11-build-with-me"


AI_PROMPT_EXPR = (
    "`You are the founder replying to a new website lead from `"
    " + ($json.company || 'their company') + `.\\n\\n"
    "Lead name: ` + $json.name + `\\n"
    "Their message: ` + $json.message + `\\n\\n"
    "Reply in 3 short sentences. Be warm, specific to what they asked, "
    "suggest a quick call, sign off as Ian. HTML formatting allowed. "
    "No subject line, body only.`"
)


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))

    nodes.append(
        set_demo_config(
            extras={
                "name": "={{ $json.body?.name || $json.name || 'there' }}",
                "email": "={{ $json.body?.email || $json.email }}",
                "company": "={{ $json.body?.company || $json.company || '' }}",
                "message": (
                    "={{ $json.body?.message || $json.message "
                    "|| 'No message provided' }}"
                ),
            },
            position=(420, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Draft Reply",
            AI_PROMPT_EXPR,
            model=MODEL_SONNET,
            temperature=0.6,
            max_tokens=450,
            position=(640, 300),
        )
    )

    # Gmail send pulls sender/subject from Demo Config and the reply body
    # directly from the AI call's response JSON. No intermediate parser —
    # keeping the node count low is part of the demo.
    reply_body_expr = (
        "$json.choices?.[0]?.message?.content "
        "|| 'Thanks for reaching out — I will be in touch shortly.'"
    )
    subject_expr = (
        "='Thanks — re: ' "
        "+ ($('Demo Config').first().json.message || 'your enquiry').slice(0, 48)"
    )
    nodes.append(
        gmail_send(
            "Send Reply",
            to_expr="={{ $('Demo Config').first().json.email }}",
            subject_expr=subject_expr,
            body_expr=(
                "={{ "
                + reply_body_expr
                + " }}"
            ),
            position=(860, 200),
        )
    )

    nodes.append(
        sheets_append(
            "Log to Google Sheet",
            "Leads_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Name": "={{ $('Demo Config').first().json.name }}",
                "Email": "={{ $('Demo Config').first().json.email }}",
                "Source": "'webhook'",
                "Intent": "'new-lead'",
                "AI_Reply_Preview": (
                    "={{ ($('AI Draft Reply').first().json.choices?.[0]?.message?.content "
                    "|| '').slice(0, 240) }}"
                ),
                "Status": "'replied'",
                "Run_ID": "={{ $('Demo Config').first().json.runId }}",
                "Workflow": "'DEMO-11'",
            },
            position=(860, 420),
        )
    )

    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({ "
                "status: 'replied', "
                "runId: $('Demo Config').first().json.runId, "
                "emailSentTo: $('Demo Config').first().json.email "
                "})"
            ),
            position=(1080, 300),
        )
    )

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    # Merge the two post-AI branches (Gmail + Sheet) via parallel edges
    # from AI Draft Reply; Respond waits on the Gmail node which is the
    # shorter of the two so the webhook responds as soon as the reply is
    # out the door.
    return {
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "AI Draft Reply", "type": "main", "index": 0}]]
        },
        "AI Draft Reply": {
            "main": [
                [
                    {"node": "Send Reply", "type": "main", "index": 0},
                    {"node": "Log to Google Sheet", "type": "main", "index": 0},
                ]
            ]
        },
        "Send Reply": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return build_workflow_envelope(WORKFLOW_NAME, nodes, connections)


if __name__ == "__main__":
    run_cli(DemoSpec(WORKFLOW_NAME, WORKFLOW_FILENAME, build_workflow))
