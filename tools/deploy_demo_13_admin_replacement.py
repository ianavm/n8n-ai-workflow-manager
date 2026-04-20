"""DEMO-13: Admin Replacement System.

The "strong opinion" demo. Narrative: one inbound webhook fires three
parallel branches, each replacing a manual admin job:

    1. AUTO-REPLY branch       -> replaces the person who replies to emails
    2. CRM UPDATE branch       -> replaces the person who updates the sheet
    3. FOLLOW-UP + PING branch -> replaces the person who schedules
                                  follow-ups + alerts the sales team

Visually satisfying to watch: three labelled branches light up at once
after the AI classifier, all three succeed before the Respond node fires.

Flow::

    Webhook Trigger
        -> Demo Config (fixture lead)
        -> DEMO_MODE Switch -> Load Fixture | Normalise Input
        -> Merge
        -> AI Classify + Draft (Sonnet, returns reply + classification)
        -> Parse Output
        -> [parallel fan-out]
            Branch A: Send Reply (Gmail)
            Branch B: Upsert CRM Sheet
            Branch C: Slack Ping + Schedule Follow-Up
        -> Merge Three Branches
        -> Audit Log
        -> Respond
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from demo_vol2_shared import (  # noqa: E402
    DemoSpec,
    MODEL_SONNET,
    audit_log,
    build_workflow_envelope,
    code_node,
    demo_mode_switch,
    gmail_send,
    openrouter_call,
    respond_to_webhook,
    run_cli,
    set_demo_config,
    sheets_append,
    sheets_update,
    slack_notify,
    uid,
    webhook_trigger,
)

WORKFLOW_NAME = "DEMO-13 Admin Replacement System"
WORKFLOW_FILENAME = "demo13_admin_replacement.json"
WEBHOOK_PATH = "demo13-admin-replacement"


FIXTURE_LEAD = {
    "name": "Sibusiso Ndlovu",
    "email": "sbu@nextgen-installs.co.za",
    "company": "NextGen Installs",
    "phone": "+27 82 555 0177",
    "source": "google-ad",
    "message": (
        "We're a 25-person solar installer in KZN. Tired of chasing service "
        "quotes and booking follow-ups manually. Looking for a system that "
        "automates lead replies + admin. Aiming to pick a partner in the "
        "next 2 weeks. Budget around R15k/mo."
    ),
}


BRAND_CONTEXT = (
    "AnyVision Media - Johannesburg AI automation agency for SA SMEs. "
    "Founder: Ian Immelman. Typical package R5k-R15k/mo."
)


CLASSIFY_PROMPT = r"""You are the sales operator for ${cfg.brand}.

For the lead below, do three things. Output STRICT JSON (no fences):
{
  "intent": "hot|question|generic|spam",
  "urgency": "low|medium|high",
  "industry": "short label",
  "leadScore": 1-10,
  "subjectLine": "...",
  "replyHtml": "<p>3-sentence personalised reply, sign as Ian, offer a 20-min slot</p>",
  "slackSummary": "one punchy slack line with name, company, ask, score"
}

Lead:
${JSON.stringify($json, null, 2)}"""


def build_nodes() -> list[dict]:
    nodes: list[dict] = []

    nodes.append(webhook_trigger(WEBHOOK_PATH, position=(200, 300)))

    nodes.append(
        set_demo_config(
            fixture_payload=FIXTURE_LEAD,
            extras={"brand": BRAND_CONTEXT},
            position=(420, 300),
        )
    )

    nodes.append(demo_mode_switch(position=(640, 300)))

    nodes.append(
        code_node(
            "Load Fixture Lead",
            """const cfg = $('Demo Config').first().json;
const l = JSON.parse(cfg.fixtureData);
return [{ json: { ...l, runId: cfg.runId, source: l.source || 'fixture' } }];""",
            position=(860, 200),
        )
    )

    nodes.append(
        code_node(
            "Normalise Live Input",
            """const cfg = $('Demo Config').first().json;
const body = $json.body || $json;
return [{
  json: {
    name: body.name || 'there',
    email: body.email || '',
    company: body.company || '',
    phone: body.phone || '',
    source: body.source || 'webhook',
    message: body.message || '',
    runId: cfg.runId,
  }
}];""",
            position=(860, 420),
        )
    )

    nodes.append(
        {
            "id": uid(),
            "name": "Merge Sources",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [1080, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(
        code_node(
            "Build Prompt",
            f"""const cfg = $('Demo Config').first().json;
const l = $input.first().json;
const prompt = `{CLASSIFY_PROMPT}`;
return [{{ json: {{ ...l, prompt }} }}];
""",
            position=(1300, 300),
        )
    )

    nodes.append(
        openrouter_call(
            "AI Classify + Draft",
            "$json.prompt",
            model=MODEL_SONNET,
            temperature=0.4,
            max_tokens=900,
            position=(1520, 300),
        )
    )

    nodes.append(
        code_node(
            "Parse Output",
            """const src = $('Build Prompt').first().json;
const resp = $input.first().json || {};
const raw = resp.choices?.[0]?.message?.content || '';
const cleaned = raw.replace(/^```(?:json)?\\s*|\\s*```$/g, '').trim();
let parsed = {};
try { parsed = cleaned ? JSON.parse(cleaned) : {}; } catch (e) {}
return [{
  json: {
    ...src,
    clientId: `CLT-${Date.now()}-${Math.floor(Math.random() * 1000)}`,
    intent: (parsed.intent || 'generic').toLowerCase(),
    urgency: (parsed.urgency || 'low').toLowerCase(),
    industry: parsed.industry || '',
    leadScore: Number(parsed.leadScore) || 5,
    subjectLine: parsed.subjectLine || `Re: ${src.company || src.name}`,
    replyHtml: parsed.replyHtml || `<p>Thanks — will follow up within one business day.</p><p>Ian</p>`,
    slackSummary: parsed.slackSummary || `New lead: ${src.name} (${src.company || '-'})`,
  }
}];""",
            position=(1740, 300),
        )
    )

    # ----- Branch A: AUTO-REPLY -----
    nodes.append(
        gmail_send(
            "[A] Send Reply",
            to_expr="={{ $json.email }}",
            subject_expr="={{ $json.subjectLine }}",
            body_expr="={{ $json.replyHtml }}",
            position=(2000, 120),
        )
    )

    nodes.append(
        sheets_append(
            "[A] Log Lead",
            "Leads_Log",
            {
                "Timestamp": "={{ new Date().toISOString() }}",
                "Name": "={{ $json.name }}",
                "Email": "={{ $json.email }}",
                "Source": "={{ $json.source }}",
                "Intent": "={{ $json.intent + '/' + $json.urgency }}",
                "AI_Reply_Preview": "={{ ($json.replyHtml || '').slice(0, 240) }}",
                "Status": "'replied'",
                "Run_ID": "={{ $json.runId }}",
                "Workflow": "'DEMO-13'",
            },
            position=(2220, 120),
        )
    )

    # ----- Branch B: CRM UPDATE -----
    nodes.append(
        sheets_update(
            "[B] Upsert CRM Client",
            "CRM_Clients",
            {
                "Client_ID": "={{ $json.clientId }}",
                "Name": "={{ $json.name }}",
                "Company": "={{ $json.company }}",
                "Email": "={{ $json.email }}",
                "Phone": "={{ $json.phone }}",
                "Last_Contacted": "={{ new Date().toISOString() }}",
                "Ask": "={{ ($json.message || '').slice(0, 240) }}",
                "Status": (
                    "={{ $json.leadScore >= 7 ? 'hot' : 'warm' }}"
                ),
                "Notes": (
                    "={{ 'industry=' + $json.industry + "
                    "' score=' + $json.leadScore }}"
                ),
                "Run_ID": "={{ $json.runId }}",
            },
            matching_column="Email",
            position=(2000, 300),
        )
    )

    # ----- Branch C: SLACK PING + FOLLOW-UP -----
    nodes.append(
        slack_notify(
            "[C] Slack Ping Sales",
            "$json.slackSummary",
            position=(2000, 480),
        )
    )

    nodes.append(
        sheets_append(
            "[C] Schedule 48h Follow-Up",
            "Follow_Ups",
            {
                "Follow_Up_ID": "={{ 'FU-' + $json.clientId }}",
                "Related_Record": "={{ $json.clientId }}",
                "Contact": "={{ $json.email }}",
                "Scheduled_For": (
                    "={{ new Date(Date.now() + 1000*60*60*48)"
                    ".toISOString().slice(0, 10) }}"
                ),
                "Type": "'lead-nurture'",
                "Status": "'due'",
                "Last_Action": "'admin-replacement-reply'",
                "Notes": (
                    "={{ 'Auto-scheduled from DEMO-13. Lead score ' + $json.leadScore }}"
                ),
            },
            position=(2220, 480),
        )
    )

    # Merge all three branches before audit/respond.
    nodes.append(
        {
            "id": uid(),
            "name": "Merge Branches",
            "type": "n8n-nodes-base.merge",
            "typeVersion": 3,
            "position": [2480, 300],
            "parameters": {"mode": "append"},
        }
    )

    nodes.append(audit_log("DEMO-13", position=(2720, 300)))

    nodes.append(
        respond_to_webhook(
            body_expr=(
                "JSON.stringify({"
                "runId: $('Demo Config').first().json.runId, "
                "status: 'three_admin_jobs_replaced', "
                "leadScore: $('Parse Output').first().json.leadScore, "
                "intent: $('Parse Output').first().json.intent "
                "})"
            ),
            position=(2960, 300),
        )
    )

    return nodes


def build_connections(_nodes: list[dict]) -> dict:
    return {
        "Webhook Trigger": {
            "main": [[{"node": "Demo Config", "type": "main", "index": 0}]]
        },
        "Demo Config": {
            "main": [[{"node": "DEMO_MODE Switch", "type": "main", "index": 0}]]
        },
        "DEMO_MODE Switch": {
            "main": [
                [{"node": "Load Fixture Lead", "type": "main", "index": 0}],
                [{"node": "Normalise Live Input", "type": "main", "index": 0}],
            ]
        },
        "Load Fixture Lead": {
            "main": [[{"node": "Merge Sources", "type": "main", "index": 0}]]
        },
        "Normalise Live Input": {
            "main": [[{"node": "Merge Sources", "type": "main", "index": 1}]]
        },
        "Merge Sources": {
            "main": [[{"node": "Build Prompt", "type": "main", "index": 0}]]
        },
        "Build Prompt": {
            "main": [[{"node": "AI Classify + Draft", "type": "main", "index": 0}]]
        },
        "AI Classify + Draft": {
            "main": [[{"node": "Parse Output", "type": "main", "index": 0}]]
        },
        "Parse Output": {
            "main": [
                [
                    {"node": "[A] Send Reply", "type": "main", "index": 0},
                    {"node": "[B] Upsert CRM Client", "type": "main", "index": 0},
                    {"node": "[C] Slack Ping Sales", "type": "main", "index": 0},
                ]
            ]
        },
        "[A] Send Reply": {
            "main": [[{"node": "[A] Log Lead", "type": "main", "index": 0}]]
        },
        "[A] Log Lead": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 0}]]
        },
        "[B] Upsert CRM Client": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 0}]]
        },
        "[C] Slack Ping Sales": {
            "main": [[{"node": "[C] Schedule 48h Follow-Up", "type": "main", "index": 0}]]
        },
        "[C] Schedule 48h Follow-Up": {
            "main": [[{"node": "Merge Branches", "type": "main", "index": 1}]]
        },
        "Merge Branches": {
            "main": [[{"node": "Audit Log", "type": "main", "index": 0}]]
        },
        "Audit Log": {
            "main": [[{"node": "Respond", "type": "main", "index": 0}]]
        },
    }


def build_workflow() -> dict:
    nodes = build_nodes()
    connections = build_connections(nodes)
    return build_workflow_envelope(WORKFLOW_NAME, nodes, connections)


if __name__ == "__main__":
    run_cli(DemoSpec(WORKFLOW_NAME, WORKFLOW_FILENAME, build_workflow))
